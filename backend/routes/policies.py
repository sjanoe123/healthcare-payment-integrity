"""Policy search and document management routes.

This router handles RAG-powered policy document search and management,
including upload, filtering, and deletion of policy documents.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, model_validator

from rag import get_store
from utils import sanitize_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["policies"])


# Pydantic models for request/response
class SearchQuery(BaseModel):
    """Query model for policy search with optional filters."""

    query: str
    n_results: int = 5
    top_k: int | None = None  # Accept frontend's top_k parameter
    sources: list[str] | None = None  # Filter by source(s)
    document_types: list[str] | None = None  # Filter by document type(s)
    effective_date: str | None = None  # Filter for policies effective at this date

    @model_validator(mode="after")
    def normalize_result_count(self) -> "SearchQuery":
        """Use top_k if n_results not explicitly set."""
        if self.top_k and self.n_results == 5:  # default was used
            object.__setattr__(self, "n_results", self.top_k)
        return self


class PolicyUploadRequest(BaseModel):
    """Request model for uploading policy documents."""

    content: str
    source: str = "user_upload"
    document_type: str = "policy"
    effective_date: str | None = None


# Routes
@router.post("/search")
async def search_policies(query: SearchQuery):
    """Search policy documents using RAG with optional filters.

    Supports filtering by:
    - sources: List of source names (e.g., ["NCCI", "LCD"])
    - document_types: List of document types (e.g., ["policy", "guideline"])
    - effective_date: ISO date string to filter for currently effective policies
    """
    store = get_store()

    if store.count() == 0:
        return {
            "query": query.query,
            "results": [],
            "total_documents": 0,
            "filters_applied": {
                "sources": query.sources,
                "document_types": query.document_types,
                "effective_date": query.effective_date,
            },
            "message": "No documents indexed. Run seed_chromadb.py to add policy documents.",
        }

    # Build filters based on query parameters
    filters: dict[str, Any] | None = None

    if query.sources or query.document_types:
        filter_conditions = []
        if query.sources:
            if len(query.sources) == 1:
                filter_conditions.append({"source": query.sources[0]})
            else:
                filter_conditions.append({"source": {"$in": query.sources}})
        if query.document_types:
            if len(query.document_types) == 1:
                filter_conditions.append({"document_type": query.document_types[0]})
            else:
                filter_conditions.append(
                    {"document_type": {"$in": query.document_types}}
                )

        if len(filter_conditions) == 1:
            filters = filter_conditions[0]
        else:
            filters = {"$and": filter_conditions}

    # Use date-aware search if effective_date specified
    if query.effective_date:
        results = store.search_current_policies(
            query.query, query.effective_date, n_results=query.n_results
        )
    else:
        results = store.search(query.query, n_results=query.n_results, filters=filters)

    return {
        "query": query.query,
        "results": results,
        "total_documents": store.count(),
        "filters_applied": {
            "sources": query.sources,
            "document_types": query.document_types,
            "effective_date": query.effective_date,
        },
    }


@router.post("/policies/upload")
async def upload_policy_document(request: PolicyUploadRequest):
    """Upload a policy document to the RAG system.

    Accepts text content and adds it to the ChromaDB vector store
    for use in policy search and rules context.
    """
    store = get_store()

    if not request.content or len(request.content.strip()) < 10:
        raise HTTPException(
            status_code=400, detail="Document content must be at least 10 characters"
        )

    # Generate document ID
    doc_hash = hashlib.sha256(request.content.encode()).hexdigest()[:12]
    doc_id = f"upload_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{doc_hash}"

    # Build metadata
    metadata = {
        "source": request.source,
        "document_type": request.document_type,
        "upload_date": datetime.now(timezone.utc).isoformat(),
    }
    if request.effective_date:
        metadata["effective_date"] = request.effective_date

    try:
        store.add_documents(
            documents=[request.content],
            metadatas=[metadata],
            ids=[doc_id],
        )

        return {
            "success": True,
            "document_id": doc_id,
            "message": "Document uploaded successfully",
            "total_documents": store.count(),
        }
    except Exception as e:
        logger.error(f"Failed to upload policy document: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to upload document: {str(e)[:200]}"
        )


@router.post("/policies/upload-file")
async def upload_policy_file(
    file: UploadFile = File(...),
    source: str = Query(default="file_upload"),
    document_type: str = Query(default="policy"),
):
    """Upload a policy document file to the RAG system.

    Supports: .txt, .md files
    PDF support requires additional dependencies.
    """
    store = get_store()

    # Sanitize filename to prevent path traversal and log injection
    raw_filename = file.filename or "unknown"
    filename = sanitize_filename(raw_filename)

    # Check file extension
    allowed_extensions = {".txt", ".md"}
    file_ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )

    try:
        # Read file content
        content = await file.read()
        text_content = content.decode("utf-8")

        if len(text_content.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Document content must be at least 10 characters",
            )

        # Generate document ID
        doc_hash = hashlib.sha256(content).hexdigest()[:12]
        doc_id = (
            f"file_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{doc_hash}"
        )

        # Build metadata
        metadata = {
            "source": source,
            "document_type": document_type,
            "filename": filename,
            "upload_date": datetime.now(timezone.utc).isoformat(),
        }

        store.add_documents(
            documents=[text_content],
            metadatas=[metadata],
            ids=[doc_id],
        )

        return {
            "success": True,
            "document_id": doc_id,
            "filename": filename,
            "message": "File uploaded successfully",
            "total_documents": store.count(),
        }

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be valid UTF-8 text",
        )
    except Exception as e:
        logger.error(f"Failed to upload policy file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)[:200]}",
        )


@router.get("/policies/sources")
async def list_policy_sources():
    """List all unique policy sources and their document counts.

    Returns dictionary mapping source names to document counts.
    Useful for building filter UIs.
    """
    store = get_store()
    return {
        "sources": store.list_sources(),
        "total_documents": store.count(),
    }


@router.get("/policies/types")
async def list_policy_types():
    """List all unique document types and their counts.

    Returns dictionary mapping document types to counts.
    Useful for building filter UIs.
    """
    store = get_store()
    return {
        "document_types": store.list_document_types(),
        "total_documents": store.count(),
    }


@router.get("/policies/{document_id}")
async def get_policy_document(document_id: str):
    """Get a specific policy document by ID.

    Returns the document content and metadata.
    """
    store = get_store()
    document = store.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


@router.delete("/policies/{document_id}")
async def delete_policy_document(document_id: str):
    """Delete a policy document by ID.

    Returns success status.
    """
    store = get_store()
    deleted = store.delete_document(document_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "success": True,
        "document_id": document_id,
        "message": "Document deleted successfully",
        "total_documents": store.count(),
    }


@router.delete("/policies/source/{source_name}")
async def delete_policies_by_source(source_name: str):
    """Delete all policy documents from a specific source.

    Useful for bulk cleanup when re-importing updated policies.
    """
    # Validate source_name to prevent unexpected behavior
    if not source_name or not source_name.strip():
        raise HTTPException(status_code=400, detail="Source name cannot be empty")
    if len(source_name) > 256:
        raise HTTPException(
            status_code=400, detail="Source name too long (max 256 characters)"
        )

    store = get_store()
    count = store.bulk_delete_by_source(source_name)

    return {
        "success": True,
        "source": source_name,
        "deleted_count": count,
        "message": f"Deleted {count} documents from source '{source_name}'",
        "total_documents": store.count(),
    }


# ============================================================
# Policy Versioning Endpoints
# ============================================================


class VersionedPolicyRequest(BaseModel):
    """Request model for adding a versioned policy document."""

    content: str
    policy_key: str  # Unique identifier like "LCD-L38604"
    source: str = "user_upload"
    document_type: str = "policy"
    effective_date: str | None = None
    expires_date: str | None = None
    replace_existing: bool = False  # If True, marks old version as not current


@router.post("/policies/versioned")
async def add_versioned_policy(request: VersionedPolicyRequest):
    """Add a versioned policy document with automatic version tracking.

    This endpoint:
    - Detects duplicate content via SHA-256 hash
    - Automatically increments version numbers
    - Optionally marks previous versions as archived

    Use this for policies that are updated periodically (e.g., LCD revisions).
    """
    store = get_store()

    if not request.content or len(request.content.strip()) < 10:
        raise HTTPException(
            status_code=400, detail="Document content must be at least 10 characters"
        )

    if not request.policy_key or len(request.policy_key.strip()) < 2:
        raise HTTPException(
            status_code=400, detail="Policy key must be at least 2 characters"
        )

    # Build metadata
    metadata = {
        "source": request.source,
        "document_type": request.document_type,
    }
    if request.effective_date:
        metadata["effective_date"] = request.effective_date
    if request.expires_date:
        metadata["expires_date"] = request.expires_date

    try:
        result = store.add_document_with_version(
            document=request.content,
            metadata=metadata,
            policy_key=request.policy_key.strip(),
            replace_existing=request.replace_existing,
        )

        return {
            "success": True,
            **result,
            "total_documents": store.count(),
        }

    except Exception as e:
        logger.error(f"Failed to add versioned policy: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to add versioned policy: {str(e)[:200]}"
        )


@router.get("/policies/versions/{policy_key}")
async def get_policy_versions(policy_key: str, include_content: bool = False):
    """Get all versions of a policy document.

    Returns version history sorted by version descending (newest first).
    """
    store = get_store()
    versions = store.get_document_versions(policy_key, include_content=include_content)

    if not versions:
        raise HTTPException(
            status_code=404, detail=f"No versions found for policy key: {policy_key}"
        )

    return {
        "policy_key": policy_key,
        "versions": versions,
        "total_versions": len(versions),
    }


@router.get("/policies/versions/{policy_key}/latest")
async def get_latest_policy_version(policy_key: str):
    """Get the latest (current) version of a policy document."""
    store = get_store()
    latest = store.get_latest_version(policy_key, include_content=True)

    if not latest:
        raise HTTPException(
            status_code=404, detail=f"No versions found for policy key: {policy_key}"
        )

    return {
        "policy_key": policy_key,
        **latest,
    }


@router.get("/policies/versions/{policy_key}/history")
async def get_policy_version_history(policy_key: str):
    """Get version history summary for a policy.

    Returns a lightweight summary without document content,
    useful for building version selector UIs.
    """
    store = get_store()
    history = store.get_version_history(policy_key)

    if not history:
        raise HTTPException(
            status_code=404, detail=f"No versions found for policy key: {policy_key}"
        )

    return {
        "policy_key": policy_key,
        "history": history,
        "total_versions": len(history),
    }


@router.get("/policies/keys")
async def list_policy_keys():
    """List all unique policy keys in the system.

    Useful for autocomplete and policy navigation UIs.
    """
    store = get_store()
    keys = store.list_policy_keys()

    return {
        "policy_keys": keys,
        "total_policies": len(keys),
    }


# ============================================================
# Policy Sync Endpoints (CMS Policy Updates)
# ============================================================


class PolicySyncRequest(BaseModel):
    """Request model for triggering a policy sync."""

    sources: list[str] | None = None  # If None, sync all sources
    force: bool = False  # Force sync even if interval hasn't elapsed


class BulkPolicyUploadRequest(BaseModel):
    """Request model for bulk uploading policy documents."""

    documents: list[dict]  # List of {content, title, source, policy_key, ...}
    source_type: str = "mln_matters"  # Default source type


@router.post("/policies/sync")
async def trigger_policy_sync(request: PolicySyncRequest):
    """Trigger a CMS policy sync job.

    This endpoint triggers synchronization of policy documents from
    configured CMS sources. Use this to update the RAG knowledge base
    with the latest policy changes.

    Args:
        sources: Optional list of source names to sync. If None, syncs all.
        force: If True, sync even if minimum interval hasn't elapsed.

    Returns:
        Sync job result with statistics.
    """
    try:
        from scheduler.cms_policy_sync import run_cms_policy_sync

        result = run_cms_policy_sync(sources=request.sources, force=request.force)
        return {
            "success": True,
            "message": "Policy sync completed",
            **result,
        }
    except Exception as e:
        logger.error(f"Policy sync failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Policy sync failed: {str(e)[:200]}"
        )


@router.get("/policies/sync/status")
async def get_policy_sync_status():
    """Get the current status of policy sync for all sources.

    Returns last sync time, status, and document counts per source.
    """
    try:
        from scheduler.cms_policy_sync import (
            CMSPolicySyncManager,
            PolicySource,
        )

        manager = CMSPolicySyncManager()
        status = {}

        for source in PolicySource:
            source_state = manager.get_source_state(source)
            last_sync = manager.get_last_sync(source)

            status[source.value] = {
                "last_sync_at": source_state.get("last_sync_at")
                if source_state
                else None,
                "last_successful_sync": source_state.get("last_successful_sync")
                if source_state
                else None,
                "total_documents": source_state.get("total_documents", 0)
                if source_state
                else 0,
                "last_status": last_sync.get("status") if last_sync else None,
                "last_documents_added": last_sync.get("documents_added", 0)
                if last_sync
                else 0,
            }

        return {
            "sources": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except ImportError:
        return {
            "sources": {},
            "message": "Policy sync module not available",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get sync status: {str(e)[:200]}"
        )


@router.get("/policies/sync/history")
async def get_policy_sync_history(
    source: str | None = Query(default=None, description="Filter by source"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Get policy sync history with optional filtering.

    Args:
        source: Optional source name to filter by
        limit: Maximum number of records to return
        offset: Pagination offset

    Returns:
        List of sync history records.
    """
    try:
        from scheduler.cms_policy_sync import (
            CMSPolicySyncManager,
            PolicySource,
        )

        manager = CMSPolicySyncManager()

        # Convert source string to enum if provided
        source_enum = None
        if source:
            try:
                source_enum = PolicySource(source)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid source: {source}. Valid sources: {[s.value for s in PolicySource]}",
                )

        history = manager.get_sync_history(
            source=source_enum, limit=limit, offset=offset
        )

        return {
            "history": history,
            "total": len(history),
            "limit": limit,
            "offset": offset,
            "source_filter": source,
        }

    except HTTPException:
        raise
    except ImportError:
        return {
            "history": [],
            "message": "Policy sync module not available",
        }
    except Exception as e:
        logger.error(f"Failed to get sync history: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get sync history: {str(e)[:200]}"
        )


@router.post("/policies/bulk-upload")
async def bulk_upload_policies(request: BulkPolicyUploadRequest):
    """Bulk upload policy documents for sync.

    This endpoint accepts a list of policy documents and indexes them
    into ChromaDB using the policy sync infrastructure.

    Each document should have:
    - content: The policy text
    - title: Document title
    - source (optional): Source name
    - policy_key (optional): Unique policy identifier
    - effective_date (optional): ISO date string
    - keywords (optional): List of keywords
    - related_codes (optional): List of procedure/diagnosis codes

    Security Note:
        This endpoint should be protected with authentication and rate limiting
        in production. Currently limited to 100 documents per request to prevent
        abuse, but additional controls (API keys, request quotas) are recommended.

    Returns:
        Summary of sync results including skipped documents with reasons.
    """
    try:
        from scheduler.cms_policy_sync import (
            CMSPolicySyncer,
            PolicyDocument,
            PolicySource,
        )

        if not request.documents:
            raise HTTPException(status_code=400, detail="No documents provided")

        if len(request.documents) > 100:
            raise HTTPException(
                status_code=400,
                detail="Maximum 100 documents per request. Use multiple requests for larger batches.",
            )

        # Convert to PolicyDocument objects, tracking skipped docs
        policy_docs = []
        skipped_docs = []
        for i, doc in enumerate(request.documents):
            if not doc.get("content") or not doc.get("title"):
                reason = []
                if not doc.get("content"):
                    reason.append("missing content")
                if not doc.get("title"):
                    reason.append("missing title")
                skipped_docs.append(
                    {
                        "index": i,
                        "title": doc.get("title", f"document_{i}"),
                        "reason": ", ".join(reason),
                    }
                )
                continue

            try:
                source_type = PolicySource(request.source_type)
            except ValueError:
                source_type = PolicySource.CUSTOM

            policy_docs.append(
                PolicyDocument(
                    content=doc["content"],
                    title=doc["title"],
                    source=source_type,
                    source_url=doc.get("source_url"),
                    policy_key=doc.get("policy_key"),
                    effective_date=doc.get("effective_date"),
                    expires_date=doc.get("expires_date"),
                    authority=doc.get("authority", "CMS"),
                    document_type=doc.get("document_type", "policy"),
                    keywords=doc.get("keywords"),
                    related_codes=doc.get("related_codes"),
                )
            )

        if not policy_docs:
            raise HTTPException(
                status_code=400,
                detail="No valid documents found. Each document requires 'content' and 'title'.",
            )

        # Sync using the CMS syncer
        syncer = CMSPolicySyncer()
        result = syncer.sync_source(
            source=PolicySource(request.source_type)
            if request.source_type in [s.value for s in PolicySource]
            else PolicySource.CUSTOM,
            documents=policy_docs,
            force=True,
        )

        return {
            "success": not result.errors,
            "documents_processed": result.documents_found,
            "documents_added": result.documents_added,
            "documents_updated": result.documents_updated,
            "documents_skipped": result.documents_skipped + len(skipped_docs),
            "skipped_documents": skipped_docs[:20],  # Limit to first 20 skipped
            "errors": result.errors[:10]
            if result.errors
            else [],  # Limit errors returned
            "duration_seconds": round(result.duration_seconds, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk upload failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Bulk upload failed: {str(e)[:200]}"
        )


@router.get("/policies/sync/sources")
async def list_sync_sources():
    """List available policy sync sources.

    Returns all configurable CMS policy sources that can be synced.
    """
    try:
        from scheduler.cms_policy_sync import PolicySource

        sources = [
            {
                "id": source.value,
                "name": source.name.replace("_", " ").title(),
                "description": _get_source_description(source),
            }
            for source in PolicySource
        ]

        return {
            "sources": sources,
            "total": len(sources),
        }
    except ImportError:
        return {
            "sources": [],
            "message": "Policy sync module not available",
        }


def _get_source_description(source) -> str:
    """Get description for a policy source."""
    from scheduler.cms_policy_sync import PolicySource

    descriptions = {
        PolicySource.MLN_MATTERS: "Medicare Learning Network articles and updates",
        PolicySource.IOM: "Internet-Only Manuals (CMS guidelines)",
        PolicySource.LCD: "Local Coverage Determination policy updates",
        PolicySource.NCD: "National Coverage Determination policy updates",
        PolicySource.NCCI: "National Correct Coding Initiative edits",
        PolicySource.CUSTOM: "Custom/user-uploaded policy documents",
    }
    return descriptions.get(source, "Policy documents")
