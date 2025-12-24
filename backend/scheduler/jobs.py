"""Sync job manager for tracking job lifecycle and history.

Provides database persistence for sync jobs including status tracking,
progress updates, and log management.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Sync job status values."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Sync job trigger type."""

    SCHEDULED = "scheduled"
    MANUAL = "manual"


class SyncJobManager:
    """Manager for sync job lifecycle and persistence.

    Handles creation, status updates, progress tracking, and logging
    for sync jobs. Uses SQLite for persistence.
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the job manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        """Ensure sync job tables exist."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Sync jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_jobs (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    sync_mode TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    started_at TEXT,
                    completed_at TEXT,
                    total_records INTEGER DEFAULT 0,
                    processed_records INTEGER DEFAULT 0,
                    failed_records INTEGER DEFAULT 0,
                    watermark_value TEXT,
                    error_message TEXT,
                    triggered_by TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (connector_id) REFERENCES connectors(id)
                )
            """)

            # Job logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_job_logs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    context TEXT,
                    FOREIGN KEY (job_id) REFERENCES sync_jobs(id)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_jobs_connector
                ON sync_jobs(connector_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_jobs_status
                ON sync_jobs(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_job_logs_job
                ON sync_job_logs(job_id)
            """)

            conn.commit()
        finally:
            conn.close()

    def create_job(
        self,
        connector_id: str,
        job_type: JobType,
        sync_mode: str,
        triggered_by: str | None = None,
    ) -> str:
        """Create a new sync job.

        Args:
            connector_id: ID of the connector to sync
            job_type: SCHEDULED or MANUAL
            sync_mode: FULL or INCREMENTAL
            triggered_by: User or system that triggered the job

        Returns:
            New job ID
        """
        job_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sync_jobs (
                    id, connector_id, job_type, sync_mode, status,
                    triggered_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    connector_id,
                    job_type.value,
                    sync_mode,
                    JobStatus.PENDING.value,
                    triggered_by,
                    created_at,
                ),
            )
            conn.commit()
            logger.info(f"Created sync job {job_id} for connector {connector_id}")
            return job_id
        finally:
            conn.close()

    def start_job(self, job_id: str) -> None:
        """Mark a job as started.

        Args:
            job_id: Job ID to start
        """
        started_at = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sync_jobs
                SET status = ?, started_at = ?
                WHERE id = ?
                """,
                (JobStatus.RUNNING.value, started_at, job_id),
            )
            conn.commit()
            logger.info(f"Started sync job {job_id}")
        finally:
            conn.close()

    def complete_job(
        self,
        job_id: str,
        success: bool,
        error_message: str | None = None,
        watermark_value: str | None = None,
    ) -> None:
        """Mark a job as completed.

        Args:
            job_id: Job ID to complete
            success: Whether job succeeded
            error_message: Error message if failed
            watermark_value: Final watermark value for incremental sync
        """
        completed_at = datetime.now(timezone.utc).isoformat()
        status = JobStatus.SUCCESS if success else JobStatus.FAILED

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sync_jobs
                SET status = ?, completed_at = ?, error_message = ?,
                    watermark_value = ?
                WHERE id = ?
                """,
                (status.value, completed_at, error_message, watermark_value, job_id),
            )
            conn.commit()
            logger.info(f"Completed sync job {job_id} with status {status.value}")
        finally:
            conn.close()

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or pending job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if job was cancelled
        """
        completed_at = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sync_jobs
                SET status = ?, completed_at = ?, error_message = ?
                WHERE id = ? AND status IN (?, ?)
                """,
                (
                    JobStatus.CANCELLED.value,
                    completed_at,
                    "Cancelled by user",
                    job_id,
                    JobStatus.PENDING.value,
                    JobStatus.RUNNING.value,
                ),
            )
            conn.commit()
            cancelled = cursor.rowcount > 0
            if cancelled:
                logger.info(f"Cancelled sync job {job_id}")
            return cancelled
        finally:
            conn.close()

    def update_progress(
        self,
        job_id: str,
        total_records: int | None = None,
        processed_records: int | None = None,
        failed_records: int | None = None,
    ) -> None:
        """Update job progress.

        Args:
            job_id: Job ID to update
            total_records: Total records to process
            processed_records: Records processed so far
            failed_records: Records that failed processing
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Build dynamic update
            updates = []
            params = []

            if total_records is not None:
                updates.append("total_records = ?")
                params.append(total_records)
            if processed_records is not None:
                updates.append("processed_records = ?")
                params.append(processed_records)
            if failed_records is not None:
                updates.append("failed_records = ?")
                params.append(failed_records)

            if updates:
                params.append(job_id)
                cursor.execute(
                    f"""
                    UPDATE sync_jobs
                    SET {", ".join(updates)}
                    WHERE id = ?
                    """,
                    params,
                )
                conn.commit()
        finally:
            conn.close()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job details.

        Args:
            job_id: Job ID

        Returns:
            Job dict or None
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sync_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_jobs(
        self,
        connector_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get sync jobs with optional filtering.

        Args:
            connector_id: Filter by connector
            status: Filter by status
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of job dicts
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            query = "SELECT * FROM sync_jobs WHERE 1=1"
            params: list[Any] = []

            if connector_id:
                query += " AND connector_id = ?"
                params.append(connector_id)
            if status:
                query += " AND status = ?"
                params.append(status.value)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_running_jobs(self, connector_id: str | None = None) -> list[dict[str, Any]]:
        """Get currently running jobs.

        Args:
            connector_id: Optional connector filter

        Returns:
            List of running job dicts
        """
        return self.get_jobs(connector_id=connector_id, status=JobStatus.RUNNING)

    def add_log(
        self,
        job_id: str,
        level: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Add a log entry to a job.

        Args:
            job_id: Job ID
            level: Log level (info, warning, error)
            message: Log message
            context: Additional context dict
        """
        import json

        log_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sync_job_logs (id, job_id, timestamp, level, message, context)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    job_id,
                    timestamp,
                    level,
                    message,
                    json.dumps(context) if context else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_logs(
        self, job_id: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get logs for a job.

        Args:
            job_id: Job ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of log dicts
        """
        import json

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM sync_job_logs
                WHERE job_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
                """,
                (job_id, limit, offset),
            )
            logs = []
            for row in cursor.fetchall():
                log = dict(row)
                if log.get("context"):
                    log["context"] = json.loads(log["context"])
                logs.append(log)
            return logs
        finally:
            conn.close()

    def get_last_successful_watermark(self, connector_id: str) -> str | None:
        """Get the watermark from the last successful sync.

        Args:
            connector_id: Connector ID

        Returns:
            Watermark value or None
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT watermark_value FROM sync_jobs
                WHERE connector_id = ? AND status = ? AND watermark_value IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT 1
                """,
                (connector_id, JobStatus.SUCCESS.value),
            )
            row = cursor.fetchone()
            return row["watermark_value"] if row else None
        finally:
            conn.close()

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """Delete old completed jobs.

        Args:
            days: Age threshold in days

        Returns:
            Number of jobs deleted
        """
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Delete logs first (foreign key)
            cursor.execute(
                """
                DELETE FROM sync_job_logs
                WHERE job_id IN (
                    SELECT id FROM sync_jobs
                    WHERE completed_at < ? AND status IN (?, ?, ?)
                )
                """,
                (
                    cutoff,
                    JobStatus.SUCCESS.value,
                    JobStatus.FAILED.value,
                    JobStatus.CANCELLED.value,
                ),
            )

            # Delete jobs
            cursor.execute(
                """
                DELETE FROM sync_jobs
                WHERE completed_at < ? AND status IN (?, ?, ?)
                """,
                (
                    cutoff,
                    JobStatus.SUCCESS.value,
                    JobStatus.FAILED.value,
                    JobStatus.CANCELLED.value,
                ),
            )

            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleaned up {deleted} old sync jobs")
            return deleted
        finally:
            conn.close()


# Global job manager instance
_job_manager_instance: SyncJobManager | None = None


def get_job_manager(db_path: str | None = None) -> SyncJobManager:
    """Get or create the global job manager instance.

    Args:
        db_path: Database path (only used on first call)

    Returns:
        Global SyncJobManager instance
    """
    import os

    global _job_manager_instance

    if _job_manager_instance is None:
        path = db_path or os.getenv("DB_PATH", "./data/prototype.db")
        _job_manager_instance = SyncJobManager(path)

    return _job_manager_instance
