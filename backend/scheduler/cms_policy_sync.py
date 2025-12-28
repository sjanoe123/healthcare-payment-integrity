"""CMS Policy Sync Job - Incremental policy document synchronization.

This module provides scheduled synchronization of healthcare policy documents
from CMS (Centers for Medicare & Medicaid Services) sources into ChromaDB
for RAG-powered policy search.

Policy Sources:
- MLN Matters articles (Medicare Learning Network)
- Internet-Only Manuals (IOM) chapters
- LCD (Local Coverage Determination) updates
- NCD (National Coverage Determination) updates
- NCCI (National Correct Coding Initiative) edits

The sync job:
1. Checks configured RSS/API sources for new or updated policies
2. Downloads and processes policy content
3. Indexes into ChromaDB with proper versioning
4. Logs all activity for HIPAA audit trail
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PolicySource(str, Enum):
    """CMS policy sources supported by the sync job."""

    MLN_MATTERS = "mln_matters"
    IOM = "internet_only_manuals"
    LCD = "lcd_updates"
    NCD = "ncd_updates"
    NCCI = "ncci_edits"
    CUSTOM = "custom"


class SyncStatus(str, Enum):
    """Sync job status values."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class PolicyDocument:
    """Represents a policy document to be indexed."""

    content: str
    title: str
    source: PolicySource
    source_url: str | None = None
    policy_key: str | None = None
    effective_date: str | None = None
    expires_date: str | None = None
    authority: str = "CMS"
    document_type: str = "policy"
    keywords: list[str] | None = None
    related_codes: list[str] | None = None


@dataclass
class SyncResult:
    """Result of a policy sync operation."""

    source: PolicySource
    documents_found: int
    documents_added: int
    documents_updated: int
    documents_skipped: int
    errors: list[str]
    duration_seconds: float


class CMSPolicySyncManager:
    """Manager for CMS policy synchronization.

    Handles tracking sync state, scheduling, and coordination of
    policy document updates from various CMS sources.
    """

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize the sync manager.

        Args:
            db_path: Path to SQLite database for state tracking
        """
        self.db_path = db_path or os.getenv("DB_PATH", "./data/prototype.db")
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        """Ensure policy sync tables exist."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Policy sync history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS policy_sync_history (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT DEFAULT 'pending',
                    documents_found INTEGER DEFAULT 0,
                    documents_added INTEGER DEFAULT 0,
                    documents_updated INTEGER DEFAULT 0,
                    documents_skipped INTEGER DEFAULT 0,
                    error_message TEXT,
                    config TEXT
                )
            """)

            # Policy source state table - tracks last sync state per source
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS policy_source_state (
                    source TEXT PRIMARY KEY,
                    last_sync_at TEXT,
                    last_successful_sync TEXT,
                    last_document_date TEXT,
                    total_documents INTEGER DEFAULT 0,
                    etag TEXT,
                    extra_state TEXT
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_policy_sync_source
                ON policy_sync_history(source)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_policy_sync_status
                ON policy_sync_history(status)
            """)

            conn.commit()
        finally:
            conn.close()

    def start_sync(
        self,
        source: PolicySource,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Start a policy sync job.

        Args:
            source: The policy source to sync
            config: Optional configuration for this sync

        Returns:
            Sync job ID
        """
        import json

        sync_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO policy_sync_history (
                    id, source, started_at, status, config
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    sync_id,
                    source.value,
                    started_at,
                    SyncStatus.RUNNING.value,
                    json.dumps(config) if config else None,
                ),
            )
            conn.commit()
            logger.info(f"Started policy sync {sync_id} for source {source.value}")
            return sync_id
        finally:
            conn.close()

    def complete_sync(
        self,
        sync_id: str,
        result: SyncResult,
    ) -> None:
        """Complete a policy sync job.

        Args:
            sync_id: The sync job ID
            result: The sync result
        """
        completed_at = datetime.now(timezone.utc).isoformat()
        status = SyncStatus.SUCCESS if not result.errors else SyncStatus.PARTIAL
        if result.documents_found == 0 and result.errors:
            status = SyncStatus.FAILED

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE policy_sync_history
                SET status = ?, completed_at = ?,
                    documents_found = ?, documents_added = ?,
                    documents_updated = ?, documents_skipped = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    completed_at,
                    result.documents_found,
                    result.documents_added,
                    result.documents_updated,
                    result.documents_skipped,
                    "; ".join(result.errors) if result.errors else None,
                    sync_id,
                ),
            )

            # Update source state
            if status in (SyncStatus.SUCCESS, SyncStatus.PARTIAL):
                cursor.execute(
                    """
                    INSERT INTO policy_source_state (source, last_sync_at, last_successful_sync)
                    VALUES (?, ?, ?)
                    ON CONFLICT(source) DO UPDATE SET
                        last_sync_at = excluded.last_sync_at,
                        last_successful_sync = excluded.last_successful_sync
                    """,
                    (result.source.value, completed_at, completed_at),
                )

            conn.commit()
            logger.info(
                f"Completed sync {sync_id}: {result.documents_added} added, "
                f"{result.documents_updated} updated, {result.documents_skipped} skipped"
            )
        finally:
            conn.close()

    def fail_sync(self, sync_id: str, error_message: str) -> None:
        """Mark a sync job as failed.

        Args:
            sync_id: The sync job ID
            error_message: The error message
        """
        completed_at = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE policy_sync_history
                SET status = ?, completed_at = ?, error_message = ?
                WHERE id = ?
                """,
                (SyncStatus.FAILED.value, completed_at, error_message, sync_id),
            )
            conn.commit()
            logger.error(f"Sync {sync_id} failed: {error_message}")
        finally:
            conn.close()

    def get_last_sync(self, source: PolicySource) -> dict[str, Any] | None:
        """Get the last sync info for a source.

        Args:
            source: The policy source

        Returns:
            Sync history dict or None
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM policy_sync_history
                WHERE source = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (source.value,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_source_state(self, source: PolicySource) -> dict[str, Any] | None:
        """Get the current state for a policy source.

        Args:
            source: The policy source

        Returns:
            Source state dict or None
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM policy_source_state WHERE source = ?",
                (source.value,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_sync_history(
        self,
        source: PolicySource | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get sync history with optional filtering.

        Args:
            source: Optional source filter
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of sync history dicts
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            query = "SELECT * FROM policy_sync_history WHERE 1=1"
            params: list[Any] = []

            if source:
                query += " AND source = ?"
                params.append(source.value)

            query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def should_sync(self, source: PolicySource, min_interval_hours: int = 6) -> bool:
        """Check if a source should be synced based on time interval.

        Args:
            source: The policy source
            min_interval_hours: Minimum hours between syncs

        Returns:
            True if sync should run
        """
        state = self.get_source_state(source)
        if not state or not state.get("last_sync_at"):
            return True

        try:
            last_sync = datetime.fromisoformat(
                state["last_sync_at"].replace("Z", "+00:00")
            )
            min_interval = timedelta(hours=min_interval_hours)
            return datetime.now(timezone.utc) - last_sync > min_interval
        except (ValueError, TypeError):
            return True


class CMSPolicySyncer:
    """Policy document syncer that fetches and indexes CMS policies.

    This class handles the actual synchronization logic for fetching
    policy documents from CMS sources and indexing them in ChromaDB.
    """

    def __init__(
        self,
        db_path: str | None = None,
        chroma_persist_dir: str | None = None,
    ) -> None:
        """Initialize the syncer.

        Args:
            db_path: Path to SQLite database
            chroma_persist_dir: Path to ChromaDB persistence directory
        """
        self.db_path = db_path or os.getenv("DB_PATH", "./data/prototype.db")
        self.chroma_persist_dir = chroma_persist_dir or os.getenv(
            "CHROMA_PERSIST_DIR", "./data/chroma"
        )
        self.sync_manager = CMSPolicySyncManager(self.db_path)

    def _get_store(self):
        """Get ChromaDB store instance."""
        from rag.chroma_store import ChromaStore

        return ChromaStore(persist_dir=self.chroma_persist_dir)

    def _log_audit_event(
        self,
        action: str,
        details: dict[str, Any] | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        """Log an audit event for HIPAA compliance.

        Args:
            action: The action being logged
            details: Additional details
            status: success or error
            error_message: Error message if status is error
        """
        try:
            from routes.audit import log_audit_event, get_db, init_audit_table

            conn = get_db()
            init_audit_table(conn)
            log_audit_event(
                conn,
                action=action,
                resource_type="policy",
                details=details,
                status=status,
                error_message=error_message,
            )
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to log audit event: {e}")

    def sync_source(
        self,
        source: PolicySource,
        documents: list[PolicyDocument] | None = None,
        force: bool = False,
    ) -> SyncResult:
        """Synchronize documents from a policy source.

        If documents is None, this will fetch from configured sources.
        If documents is provided, those documents will be indexed.

        Args:
            source: The policy source to sync
            documents: Optional list of documents to index (for manual/batch upload)
            force: Force sync even if interval hasn't elapsed

        Returns:
            SyncResult with sync statistics
        """
        import time

        start_time = time.time()

        # Check if sync is needed
        if not force and not self.sync_manager.should_sync(source):
            logger.info(f"Skipping sync for {source.value} - too soon since last sync")
            return SyncResult(
                source=source,
                documents_found=0,
                documents_added=0,
                documents_updated=0,
                documents_skipped=0,
                errors=["Sync skipped - interval not elapsed"],
                duration_seconds=0,
            )

        # Start sync tracking
        sync_id = self.sync_manager.start_sync(source)

        # Log audit event
        self._log_audit_event(
            action="policy.sync_start",
            details={"source": source.value, "sync_id": sync_id},
        )

        try:
            # If no documents provided, fetch from source
            if documents is None:
                documents = self._fetch_from_source(source)

            store = self._get_store()
            added = 0
            updated = 0
            skipped = 0
            errors: list[str] = []

            for doc in documents:
                try:
                    result = self._index_document(store, doc)
                    if result.get("is_duplicate"):
                        skipped += 1
                    elif result.get("replaced_id"):
                        updated += 1
                    else:
                        added += 1
                except Exception as e:
                    errors.append(f"Failed to index {doc.title}: {str(e)}")
                    logger.error(f"Failed to index document: {e}")

            duration = time.time() - start_time

            result = SyncResult(
                source=source,
                documents_found=len(documents),
                documents_added=added,
                documents_updated=updated,
                documents_skipped=skipped,
                errors=errors,
                duration_seconds=duration,
            )

            self.sync_manager.complete_sync(sync_id, result)

            # Log audit event
            self._log_audit_event(
                action="policy.sync_complete",
                details={
                    "source": source.value,
                    "sync_id": sync_id,
                    "documents_added": added,
                    "documents_updated": updated,
                    "documents_skipped": skipped,
                    "duration_seconds": round(duration, 2),
                },
            )

            return result

        except Exception as e:
            error_msg = str(e)
            self.sync_manager.fail_sync(sync_id, error_msg)

            # Log audit event
            self._log_audit_event(
                action="policy.sync_failed",
                details={"source": source.value, "sync_id": sync_id},
                status="error",
                error_message=error_msg,
            )

            return SyncResult(
                source=source,
                documents_found=0,
                documents_added=0,
                documents_updated=0,
                documents_skipped=0,
                errors=[error_msg],
                duration_seconds=time.time() - start_time,
            )

    def _fetch_from_source(self, source: PolicySource) -> list[PolicyDocument]:
        """Fetch documents from a policy source.

        This is a placeholder that can be expanded with actual RSS/API
        integrations for different CMS sources.

        Args:
            source: The policy source to fetch from

        Returns:
            List of PolicyDocument objects
        """
        # This would be replaced with actual source-specific fetching logic
        # For now, return empty list - documents should be provided explicitly
        # or via the upload endpoint

        logger.info(f"Fetch from {source.value} - no automatic fetch configured")
        return []

    def _index_document(
        self,
        store,
        doc: PolicyDocument,
    ) -> dict[str, Any]:
        """Index a single policy document into ChromaDB.

        Args:
            store: ChromaDB store instance
            doc: The document to index

        Returns:
            Result dict from add_document_with_version
        """
        # Generate policy key if not provided
        policy_key = doc.policy_key
        if not policy_key:
            # Create a stable key from title and source for deduplication.
            # NOTE: MD5 is used here for uniqueness/deduplication only, not for
            # cryptographic security. It provides a short, stable identifier from
            # the document source and title. SHA256 would also work but produces
            # longer hashes; the 12-char truncation makes MD5 sufficient.
            key_source = f"{doc.source.value}_{doc.title}"
            policy_key = hashlib.md5(key_source.encode()).hexdigest()[:12]
            policy_key = f"{doc.source.value.upper()}_{policy_key}"

        # Build metadata
        metadata = {
            "source": doc.source.value,
            "source_url": doc.source_url,
            "title": doc.title,
            "authority": doc.authority,
            "document_type": doc.document_type,
        }

        if doc.effective_date:
            metadata["effective_date"] = doc.effective_date
        if doc.expires_date:
            metadata["expires_date"] = doc.expires_date
        if doc.keywords:
            metadata["keywords"] = ",".join(doc.keywords)
        if doc.related_codes:
            metadata["related_codes"] = ",".join(doc.related_codes)

        # Use versioning to handle updates
        return store.add_document_with_version(
            document=doc.content,
            metadata=metadata,
            policy_key=policy_key,
            replace_existing=True,  # Keep latest as current
        )

    def sync_all_sources(self, force: bool = False) -> dict[str, SyncResult]:
        """Sync all configured policy sources.

        Args:
            force: Force sync even if interval hasn't elapsed

        Returns:
            Dictionary mapping source name to SyncResult
        """
        results = {}
        for source in PolicySource:
            if source != PolicySource.CUSTOM:
                result = self.sync_source(source, force=force)
                results[source.value] = result
        return results


# Scheduled job function
def run_cms_policy_sync(
    sources: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Run CMS policy sync as a scheduled job.

    This function is designed to be called by APScheduler.

    Args:
        sources: Optional list of source names to sync. If None, sync all.
        force: Force sync even if interval hasn't elapsed.

    Returns:
        Summary of sync results
    """
    syncer = CMSPolicySyncer()

    if sources:
        results = {}
        for source_name in sources:
            try:
                source = PolicySource(source_name)
                result = syncer.sync_source(source, force=force)
                results[source_name] = {
                    "status": "success" if not result.errors else "partial",
                    "documents_added": result.documents_added,
                    "documents_updated": result.documents_updated,
                    "documents_skipped": result.documents_skipped,
                    "errors": result.errors,
                    "duration_seconds": result.duration_seconds,
                }
            except ValueError:
                results[source_name] = {
                    "status": "error",
                    "error": f"Unknown source: {source_name}",
                }
    else:
        all_results = syncer.sync_all_sources(force=force)
        results = {
            name: {
                "status": "success" if not r.errors else "partial",
                "documents_added": r.documents_added,
                "documents_updated": r.documents_updated,
                "documents_skipped": r.documents_skipped,
                "errors": r.errors,
                "duration_seconds": r.duration_seconds,
            }
            for name, r in all_results.items()
        }

    total_added = sum(r.get("documents_added", 0) for r in results.values())
    total_updated = sum(r.get("documents_updated", 0) for r in results.values())

    logger.info(f"Policy sync complete: {total_added} added, {total_updated} updated")

    return {
        "sources": results,
        "total_added": total_added,
        "total_updated": total_updated,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Global syncer instance
# NOTE: This singleton pattern is NOT thread-safe. It is designed for use with
# APScheduler's single-threaded executors or sequential job execution.
# If multi-threaded access is needed, add threading.Lock around instance creation.
_syncer_instance: CMSPolicySyncer | None = None


def get_policy_syncer(
    db_path: str | None = None,
    chroma_persist_dir: str | None = None,
) -> CMSPolicySyncer:
    """Get or create the global policy syncer instance.

    Note:
        This uses a simple singleton pattern without thread locks. It is intended
        for single-threaded scheduler use. For concurrent access, consider adding
        a threading.Lock or using dependency injection instead.

    Args:
        db_path: Database path (only used on first call)
        chroma_persist_dir: ChromaDB path (only used on first call)

    Returns:
        Global CMSPolicySyncer instance
    """
    global _syncer_instance

    if _syncer_instance is None:
        _syncer_instance = CMSPolicySyncer(db_path, chroma_persist_dir)

    return _syncer_instance
