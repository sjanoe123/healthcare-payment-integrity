"""ChromaDB vector store for RAG.

This module provides a wrapper around ChromaDB for storing and retrieving
healthcare policy documents. Features include:
- Semantic search with metadata filtering
- Policy versioning with automatic version tracking
- Deduplication via content hashing
- Date-aware policy lookups
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


def _compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of document content for deduplication.

    Args:
        content: Document text content

    Returns:
        First 16 characters of hex-encoded SHA-256 hash
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _increment_version(current_version: str | None) -> str:
    """Increment a version string.

    Supports formats:
    - "1" -> "2"
    - "1.0" -> "1.1"
    - "2024.1" -> "2024.2"
    - None -> "1"

    Args:
        current_version: Existing version string or None

    Returns:
        Incremented version string
    """
    if not current_version:
        return "1"

    # Try to increment last numeric component
    parts = current_version.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except ValueError:
        # If last part isn't numeric, append .1
        return f"{current_version}.1"


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse a date string into a datetime object.

    Handles multiple formats:
    - ISO 8601: "2024-01-15"
    - US format: "01/15/2024"
    - Compact: "20240115"

    Returns None if parsing fails.
    """
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",  # ISO 8601
        "%m/%d/%Y",  # US format
        "%d/%m/%Y",  # EU format
        "%Y%m%d",  # Compact
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


# Simple cache for metadata aggregations
_metadata_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 60  # Cache for 1 minute

# Lock for thread-safe version replacement operations
_version_lock = threading.Lock()


class ChromaStore:
    """Simple ChromaDB wrapper for policy document retrieval."""

    def __init__(
        self, persist_dir: str | None = None, collection_name: str = "policies"
    ):
        self.persist_dir = persist_dir or os.getenv(
            "CHROMA_PERSIST_DIR", "./data/chroma"
        )
        self.collection_name = collection_name

        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Healthcare policy documents for RAG"},
        )

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """Add documents to the collection."""
        if not documents:
            return

        # Generate IDs if not provided
        if ids is None:
            existing_count = self.collection.count()
            ids = [f"doc_{existing_count + i}" for i in range(len(documents))]

        # Default metadata if not provided
        if metadatas is None:
            metadatas = [{"source": "unknown"} for _ in documents]

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        self.invalidate_cache()  # Clear cached counts

    def search(
        self,
        query: str,
        n_results: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for relevant documents with optional metadata filters.

        Args:
            query: Search query text
            n_results: Maximum number of results to return
            filters: Optional metadata filters using ChromaDB where clause syntax.
                     Examples:
                     - {"source": "NCCI"} - exact match
                     - {"source": {"$in": ["NCCI", "LCD"]}} - match any
                     - {"$and": [{"source": "CMS"}, {"document_type": "policy"}]}

        Returns:
            List of matching documents with content, metadata, distance, and score.
        """
        if self.collection.count() == 0:
            return []

        query_kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
        }

        if filters:
            query_kwargs["where"] = filters

        results = self.collection.query(**query_kwargs)

        # Format results
        formatted = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i] if results["distances"] else None
                # Convert distance to similarity score (0-1, higher is better)
                # ChromaDB uses cosine distance by default which ranges from 0-2:
                #   0 = identical vectors, 2 = opposite vectors
                # Formula: score = 1 - (distance / 2)
                # Very dissimilar embeddings (distance > 2) get clamped to 0 via max()
                score = (
                    max(0.0, min(1.0, 1 - (distance / 2)))
                    if distance is not None
                    else 0.0
                )

                formatted.append(
                    {
                        "content": doc,
                        "metadata": results["metadatas"][0][i]
                        if results["metadatas"]
                        else {},
                        "distance": distance,
                        "score": round(score, 4),  # Similarity score for frontend
                        "id": results["ids"][0][i] if results["ids"] else None,
                    }
                )

        return formatted

    def count(self) -> int:
        """Return number of documents in collection."""
        return self.collection.count()

    def clear(self) -> None:
        """Clear all documents from collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Healthcare policy documents for RAG"},
        )

    def search_by_source(
        self,
        query: str,
        sources: list[str],
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search within specific sources only.

        Args:
            query: Search query text
            sources: List of source names to search within
            n_results: Maximum number of results

        Returns:
            Filtered search results from specified sources only.
        """
        if not sources:
            return self.search(query, n_results)

        filters = (
            {"source": {"$in": sources}} if len(sources) > 1 else {"source": sources[0]}
        )
        return self.search(query, n_results, filters)

    def search_by_document_type(
        self,
        query: str,
        document_types: list[str],
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search within specific document types only.

        Args:
            query: Search query text
            document_types: List of document types (e.g., ["policy", "guideline"])
            n_results: Maximum number of results

        Returns:
            Filtered search results from specified document types only.
        """
        if not document_types:
            return self.search(query, n_results)

        filters = (
            {"document_type": {"$in": document_types}}
            if len(document_types) > 1
            else {"document_type": document_types[0]}
        )
        return self.search(query, n_results, filters)

    def search_current_policies(
        self,
        query: str,
        reference_date: str,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for policies effective at a given date.

        Args:
            query: Search query text
            reference_date: ISO 8601 date string (e.g., "2024-01-15")
            n_results: Maximum number of results

        Returns:
            Policies where effective_date <= reference_date and
            (expires_date is null OR expires_date > reference_date)
        """
        # ChromaDB doesn't support complex date comparisons directly,
        # so we filter post-query
        results = self.search(query, n_results * 3)  # Fetch more to filter

        # Parse reference date once
        ref_dt = _parse_date(reference_date)
        if not ref_dt:
            # If reference date is invalid, return unfiltered results
            return results[:n_results]

        filtered = []
        for r in results:
            meta = r.get("metadata", {})
            effective_str = meta.get("effective_date")
            expires_str = meta.get("expires_date")

            # Parse dates for proper comparison (handles multiple formats)
            effective_dt = _parse_date(effective_str)
            expires_dt = _parse_date(expires_str)

            # Include if no date constraints or dates are valid
            if effective_dt and effective_dt > ref_dt:
                continue  # Not yet effective
            if expires_dt and expires_dt <= ref_dt:
                continue  # Already expired

            filtered.append(r)
            if len(filtered) >= n_results:
                break

        return filtered

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Get a single document by ID.

        Args:
            document_id: The document ID to retrieve

        Returns:
            Document dict with content, metadata, and id, or None if not found.
        """
        try:
            result = self.collection.get(ids=[document_id])
            if result["documents"] and result["documents"][0]:
                return {
                    "id": document_id,
                    "content": result["documents"][0],
                    "metadata": result["metadatas"][0] if result["metadatas"] else {},
                }
        except Exception as e:
            logger.warning(f"Failed to get document {document_id}: {e}")
        return None

    def _get_cached_or_compute(
        self, cache_key: str, compute_fn: callable
    ) -> dict[str, int]:
        """Get cached value or compute and cache it.

        Uses module-level cache with TTL to avoid loading all docs repeatedly.
        """
        now = time.time()
        if cache_key in _metadata_cache:
            cached_time, cached_value = _metadata_cache[cache_key]
            if now - cached_time < _CACHE_TTL_SECONDS:
                return cached_value

        # Compute and cache
        value = compute_fn()
        _metadata_cache[cache_key] = (now, value)
        return value

    def _compute_source_counts(self) -> dict[str, int]:
        """Compute source counts from all documents."""
        all_docs = self.collection.get()
        source_counts: dict[str, int] = {}

        if all_docs["metadatas"]:
            for meta in all_docs["metadatas"]:
                source = meta.get("source", "unknown")
                source_counts[source] = source_counts.get(source, 0) + 1

        return source_counts

    def _compute_type_counts(self) -> dict[str, int]:
        """Compute document type counts from all documents."""
        all_docs = self.collection.get()
        type_counts: dict[str, int] = {}

        if all_docs["metadatas"]:
            for meta in all_docs["metadatas"]:
                doc_type = meta.get("document_type", "unknown")
                type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

        return type_counts

    def list_sources(self) -> dict[str, int]:
        """List all unique sources and their document counts.

        Results are cached for 60 seconds to avoid loading all documents
        on every call.

        Returns:
            Dictionary mapping source names to document counts.
        """
        cache_key = f"{self.collection_name}:sources"
        return self._get_cached_or_compute(cache_key, self._compute_source_counts)

    def list_document_types(self) -> dict[str, int]:
        """List all unique document types and their counts.

        Results are cached for 60 seconds to avoid loading all documents
        on every call.

        Returns:
            Dictionary mapping document types to counts.
        """
        cache_key = f"{self.collection_name}:types"
        return self._get_cached_or_compute(cache_key, self._compute_type_counts)

    def invalidate_cache(self) -> None:
        """Invalidate the metadata cache.

        Call this after adding or deleting documents to ensure fresh counts.
        """
        keys_to_remove = [
            k for k in _metadata_cache if k.startswith(self.collection_name)
        ]
        for k in keys_to_remove:
            _metadata_cache.pop(k, None)

    def delete_document(self, document_id: str) -> bool:
        """Delete a document by ID.

        Args:
            document_id: The document ID to delete

        Returns:
            True if deleted, False if not found.
        """
        try:
            # Check if exists first
            existing = self.collection.get(ids=[document_id])
            if not existing["ids"]:
                return False
            self.collection.delete(ids=[document_id])
            self.invalidate_cache()  # Clear cached counts
            return True
        except Exception as e:
            logger.warning(f"Failed to delete document {document_id}: {e}")
            return False

    def bulk_delete_by_source(self, source: str) -> int:
        """Delete all documents from a specific source.

        Args:
            source: The source name to delete documents from

        Returns:
            Number of documents deleted.
        """
        # Get all documents with this source
        all_docs = self.collection.get(where={"source": source})

        if not all_docs["ids"]:
            return 0

        count = len(all_docs["ids"])
        self.collection.delete(ids=all_docs["ids"])
        self.invalidate_cache()  # Clear cached counts
        return count

    def update_metadata(
        self,
        document_id: str,
        metadata_updates: dict[str, Any],
    ) -> bool:
        """Update metadata for an existing document.

        Args:
            document_id: The document ID to update
            metadata_updates: Dictionary of metadata fields to update

        Returns:
            True if updated, False if document not found.
        """
        try:
            existing = self.collection.get(ids=[document_id])
            if not existing["ids"]:
                return False

            # Merge existing metadata with updates
            current_metadata = existing["metadatas"][0] if existing["metadatas"] else {}
            updated_metadata = {**current_metadata, **metadata_updates}

            self.collection.update(
                ids=[document_id],
                metadatas=[updated_metadata],
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to update metadata for {document_id}: {e}")
            return False

    # ================================================================
    # Policy Versioning Methods
    # ================================================================

    def add_document_with_version(
        self,
        document: str,
        metadata: dict[str, Any],
        policy_key: str,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        """Add a versioned policy document with automatic version tracking.

        This method handles policy versioning by:
        1. Computing a content hash for deduplication
        2. Checking if identical content already exists
        3. Creating a new version or replacing existing

        Thread-safe: Uses a lock to prevent race conditions when multiple
        requests try to add versions of the same policy concurrently.

        Args:
            document: The policy document text content
            metadata: Document metadata (source, document_type, effective_date, etc.)
            policy_key: Unique key identifying this policy (e.g., "LCD-L38604")
            replace_existing: If True, archives old version and replaces.
                            If False, adds as new version alongside existing.

        Returns:
            Dict with:
            - document_id: The new document's ID
            - version: The assigned version number
            - is_duplicate: True if content was already indexed
            - replaced_id: ID of replaced document (if replace_existing=True)

        Example:
            >>> store.add_document_with_version(
            ...     document="Policy content...",
            ...     metadata={"source": "LCD", "effective_date": "2024-01-01"},
            ...     policy_key="LCD-L38604",
            ...     replace_existing=True
            ... )
            {"document_id": "LCD-L38604_v3", "version": "3", ...}
        """
        content_hash = _compute_content_hash(document)

        # Use lock to prevent race conditions in version replacement
        with _version_lock:
            # Check for existing versions of this policy
            existing_versions = self.get_document_versions(policy_key)

            # Check for duplicate content
            for existing in existing_versions:
                if existing.get("metadata", {}).get("content_hash") == content_hash:
                    return {
                        "document_id": existing["id"],
                        "version": existing.get("metadata", {}).get("version", "1"),
                        "is_duplicate": True,
                        "replaced_id": None,
                        "message": "Identical content already exists",
                    }

            # Determine new version number
            if existing_versions:
                latest = existing_versions[0]  # Already sorted by version desc
                latest_version = latest.get("metadata", {}).get("version", "1")
                new_version = _increment_version(latest_version)
            else:
                new_version = "1"

            # Build document ID with version
            doc_id = f"{policy_key}_v{new_version}"

            # Enhance metadata with versioning info
            enhanced_metadata = {
                **metadata,
                "policy_key": policy_key,
                "version": new_version,
                "content_hash": content_hash,
                "is_current": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            replaced_id = None

            # Handle replacement mode - atomic with version check
            if replace_existing and existing_versions:
                # Mark previous version as not current
                for old_doc in existing_versions:
                    if old_doc.get("metadata", {}).get("is_current"):
                        self.update_metadata(old_doc["id"], {"is_current": False})
                        replaced_id = old_doc["id"]
                        break

            # Add the new document
            self.add_documents(
                documents=[document],
                metadatas=[enhanced_metadata],
                ids=[doc_id],
            )

            # Invalidate policy_keys cache since we added a new policy
            policy_keys_cache_key = f"{self.collection_name}:policy_keys"
            _metadata_cache.pop(policy_keys_cache_key, None)

        return {
            "document_id": doc_id,
            "version": new_version,
            "is_duplicate": False,
            "replaced_id": replaced_id,
            "message": f"Added version {new_version}",
        }

    def get_document_versions(
        self,
        policy_key: str,
        include_content: bool = False,
    ) -> list[dict[str, Any]]:
        """Get all versions of a policy document.

        Args:
            policy_key: The unique policy key (e.g., "LCD-L38604")
            include_content: If True, include document content in results

        Returns:
            List of document versions, sorted by version descending (newest first).
            Each entry contains id, metadata, and optionally content.
        """
        try:
            # Query for all documents with this policy_key
            results = self.collection.get(
                where={"policy_key": policy_key},
                include=["metadatas", "documents"]
                if include_content
                else ["metadatas"],
            )

            if not results["ids"]:
                return []

            versions = []
            for i, doc_id in enumerate(results["ids"]):
                entry = {
                    "id": doc_id,
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                }
                if include_content and results.get("documents"):
                    entry["content"] = results["documents"][i]
                versions.append(entry)

            # Sort by version descending (newest first)
            def version_sort_key(item: dict) -> tuple:
                version = item.get("metadata", {}).get("version", "0")
                # Split version and convert to tuple of ints for proper sorting
                try:
                    parts = [int(p) for p in version.split(".")]
                    return tuple(parts)
                except ValueError:
                    return (0,)

            versions.sort(key=version_sort_key, reverse=True)
            return versions

        except Exception as e:
            logger.warning(f"Failed to get document versions for {policy_key}: {e}")
            return []

    def get_latest_version(
        self,
        policy_key: str,
        include_content: bool = True,
    ) -> dict[str, Any] | None:
        """Get the latest (current) version of a policy document.

        Args:
            policy_key: The unique policy key (e.g., "LCD-L38604")
            include_content: If True, include document content

        Returns:
            The latest version document, or None if not found.
        """
        try:
            # First try to find the document marked as current
            results = self.collection.get(
                where={"$and": [{"policy_key": policy_key}, {"is_current": True}]},
                include=["metadatas", "documents"]
                if include_content
                else ["metadatas"],
            )

            if results["ids"]:
                entry = {
                    "id": results["ids"][0],
                    "metadata": results["metadatas"][0] if results["metadatas"] else {},
                }
                if include_content and results.get("documents"):
                    entry["content"] = results["documents"][0]
                return entry

            # Fallback: get all versions and return the highest
            versions = self.get_document_versions(policy_key, include_content)
            return versions[0] if versions else None

        except Exception as e:
            logger.warning(f"Failed to get latest version for {policy_key}: {e}")
            return None

    def list_policy_keys(self) -> list[str]:
        """List all unique policy keys in the collection.

        Returns:
            List of unique policy_key values.
        """
        cache_key = f"{self.collection_name}:policy_keys"

        def compute():
            all_docs = self.collection.get(include=["metadatas"])
            keys = set()
            if all_docs["metadatas"]:
                for meta in all_docs["metadatas"]:
                    key = meta.get("policy_key")
                    if key:
                        keys.add(key)
            return sorted(keys)

        return self._get_cached_or_compute(cache_key, compute)

    def get_version_history(
        self,
        policy_key: str,
    ) -> list[dict[str, Any]]:
        """Get version history summary for a policy.

        Args:
            policy_key: The unique policy key

        Returns:
            List of version summaries with id, version, created_at, is_current.
        """
        versions = self.get_document_versions(policy_key, include_content=False)
        return [
            {
                "id": v["id"],
                "version": v.get("metadata", {}).get("version", "?"),
                "created_at": v.get("metadata", {}).get("created_at"),
                "is_current": v.get("metadata", {}).get("is_current", False),
                "effective_date": v.get("metadata", {}).get("effective_date"),
                "expires_date": v.get("metadata", {}).get("expires_date"),
            }
            for v in versions
        ]


# Global instance
_store: ChromaStore | None = None


def get_store() -> ChromaStore:
    """Get or create the global ChromaDB store."""
    global _store
    if _store is None:
        _store = ChromaStore()
    return _store
