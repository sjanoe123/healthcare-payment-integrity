"""Sync worker for executing data synchronization jobs.

Handles the actual execution of sync jobs including extraction,
transformation, and loading of data from connectors.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .jobs import JobType, SyncJobManager, get_job_manager

logger = logging.getLogger(__name__)


# Thread-local storage for database connections
_thread_local = threading.local()


@contextmanager
def get_db_connection(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """Get a database connection with proper management.

    Uses thread-local storage to reuse connections within the same thread.
    Connections are properly closed when the context exits.

    Args:
        db_path: Path to SQLite database

    Yields:
        SQLite connection
    """
    path = db_path or os.getenv("DB_PATH", "./data/prototype.db")

    # Get or create connection for this thread
    if not hasattr(_thread_local, "connections"):
        _thread_local.connections = {}

    if path not in _thread_local.connections:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        _thread_local.connections[path] = conn

    try:
        yield _thread_local.connections[path]
    except Exception:
        # On error, close and remove the connection
        conn = _thread_local.connections.pop(path, None)
        if conn:
            conn.close()
        raise


class SyncWorker:
    """Worker for executing sync jobs.

    Coordinates the extraction of data from connectors and
    tracks progress through the job manager.
    """

    def __init__(
        self,
        job_manager: SyncJobManager | None = None,
        db_path: str | None = None,
    ) -> None:
        """Initialize the sync worker.

        Args:
            job_manager: Job manager instance
            db_path: Database path for default job manager
        """
        self.job_manager = job_manager or get_job_manager(db_path)
        self._running_jobs: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def execute_sync(
        self,
        connector_id: str,
        job_type: JobType = JobType.MANUAL,
        sync_mode: str = "incremental",
        triggered_by: str | None = None,
    ) -> str:
        """Execute a sync job for a connector.

        Args:
            connector_id: Connector to sync
            job_type: SCHEDULED or MANUAL
            sync_mode: FULL or INCREMENTAL
            triggered_by: User or system that triggered

        Returns:
            Job ID
        """
        # Create job record
        job_id = self.job_manager.create_job(
            connector_id=connector_id,
            job_type=job_type,
            sync_mode=sync_mode,
            triggered_by=triggered_by,
        )

        # Create cancellation event
        cancel_event = threading.Event()
        with self._lock:
            self._running_jobs[job_id] = cancel_event

        # Start job in background thread
        thread = threading.Thread(
            target=self._run_sync,
            args=(job_id, connector_id, sync_mode, cancel_event),
            daemon=True,
        )
        thread.start()

        return job_id

    def cancel_sync(self, job_id: str) -> bool:
        """Cancel a running sync job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancellation was signaled
        """
        with self._lock:
            cancel_event = self._running_jobs.get(job_id)
            if cancel_event:
                cancel_event.set()
                return self.job_manager.cancel_job(job_id)
        return False

    def _run_sync(
        self,
        job_id: str,
        connector_id: str,
        sync_mode: str,
        cancel_event: threading.Event,
    ) -> None:
        """Run the sync job.

        Args:
            job_id: Job ID
            connector_id: Connector to sync
            sync_mode: FULL or INCREMENTAL
            cancel_event: Event to signal cancellation
        """
        try:
            self.job_manager.start_job(job_id)
            self.job_manager.add_log(
                job_id,
                "info",
                f"Starting {sync_mode} sync for connector {connector_id}",
            )

            # Get connector configuration
            connector_config = self._get_connector_config(connector_id)
            if not connector_config:
                raise ValueError(f"Connector {connector_id} not found")

            connector_type = connector_config.get("connector_type")
            subtype = connector_config.get("subtype")
            config = connector_config.get("connection_config", {})

            self.job_manager.add_log(
                job_id,
                "info",
                f"Connector type: {connector_type}/{subtype}",
                {"config_keys": list(config.keys())},
            )

            # Create connector instance
            connector = self._create_connector(
                connector_id, connector_type, subtype, config
            )

            if not connector:
                raise ValueError(
                    f"Unsupported connector type: {connector_type}/{subtype}"
                )

            # Get watermark for incremental sync
            watermark_value = None
            if sync_mode == "incremental":
                watermark_value = self.job_manager.get_last_successful_watermark(
                    connector_id
                )
                if watermark_value:
                    self.job_manager.add_log(
                        job_id,
                        "info",
                        f"Using watermark: {watermark_value}",
                    )

            # Connect and extract data
            connector.connect()
            self.job_manager.add_log(job_id, "info", "Connected to data source")

            # Import SyncMode
            from ..connectors.models import SyncMode

            mode = SyncMode.INCREMENTAL if sync_mode == "incremental" else SyncMode.FULL

            total_records = 0
            processed_records = 0
            failed_records = 0
            final_watermark = watermark_value

            try:
                for batch in connector.extract(mode, watermark_value):
                    # Check for cancellation
                    if cancel_event.is_set():
                        self.job_manager.add_log(
                            job_id, "warning", "Sync cancelled by user"
                        )
                        break

                    batch_size = len(batch)
                    total_records += batch_size

                    # Process batch (transform and load)
                    try:
                        processed, failed = self._process_batch(
                            job_id, connector_id, batch, connector_config
                        )
                        processed_records += processed
                        failed_records += failed

                        # Update watermark from last record
                        watermark_col = config.get("watermark_column")
                        if watermark_col and batch:
                            last_record = batch[-1]
                            if watermark_col in last_record:
                                final_watermark = str(last_record[watermark_col])

                    except Exception as e:
                        failed_records += batch_size
                        self.job_manager.add_log(
                            job_id,
                            "error",
                            f"Batch processing failed: {str(e)}",
                            {"batch_size": batch_size},
                        )

                    # Update progress
                    self.job_manager.update_progress(
                        job_id,
                        total_records=total_records,
                        processed_records=processed_records,
                        failed_records=failed_records,
                    )

            finally:
                connector.disconnect()

            # Complete job
            if cancel_event.is_set():
                self.job_manager.cancel_job(job_id)
            else:
                self.job_manager.complete_job(
                    job_id,
                    success=True,
                    watermark_value=final_watermark,
                )
                self.job_manager.add_log(
                    job_id,
                    "info",
                    f"Sync completed: {processed_records}/{total_records} records",
                    {
                        "total": total_records,
                        "processed": processed_records,
                        "failed": failed_records,
                    },
                )

                # Update connector's last sync info
                self._update_connector_sync_status(
                    connector_id, "success", final_watermark
                )

        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Sync job {job_id} failed: {error_msg}")
            self.job_manager.add_log(
                job_id,
                "error",
                f"Sync failed: {error_msg}",
                {"traceback": traceback.format_exc()},
            )
            self.job_manager.complete_job(
                job_id, success=False, error_message=error_msg
            )
            self._update_connector_sync_status(connector_id, "failed", None)

        finally:
            # Clean up
            with self._lock:
                self._running_jobs.pop(job_id, None)

    def _get_connector_config(self, connector_id: str) -> dict[str, Any] | None:
        """Get connector configuration from database.

        Args:
            connector_id: Connector ID

        Returns:
            Connector config dict or None
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM connectors WHERE id = ?", (connector_id,))
            row = cursor.fetchone()
            if not row:
                return None

            config = dict(row)
            # Parse JSON config
            if config.get("connection_config"):
                config["connection_config"] = json.loads(config["connection_config"])
            return config

    def _create_connector(
        self,
        connector_id: str,
        connector_type: str,
        subtype: str,
        config: dict[str, Any],
    ) -> Any:
        """Create a connector instance.

        Args:
            connector_id: Connector ID
            connector_type: Type (database, api, file)
            subtype: Subtype (postgresql, mysql, etc.)
            config: Connection configuration

        Returns:
            Connector instance or None
        """
        if connector_type == "database":
            if subtype == "postgresql":
                from ..connectors.database import PostgreSQLConnector

                return PostgreSQLConnector(
                    connector_id=connector_id,
                    name=config.get("name", connector_id),
                    config=config,
                )
            elif subtype == "mysql":
                from ..connectors.database import MySQLConnector

                return MySQLConnector(
                    connector_id=connector_id,
                    name=config.get("name", connector_id),
                    config=config,
                )

        # Add more connector types as implemented
        return None

    def _process_batch(
        self,
        job_id: str,
        connector_id: str,
        batch: list[dict[str, Any]],
        connector_config: dict[str, Any],
    ) -> tuple[int, int]:
        """Process a batch of records.

        Args:
            job_id: Current job ID
            connector_id: Connector ID
            batch: List of records
            connector_config: Connector configuration

        Returns:
            Tuple of (processed_count, failed_count)
        """
        # For now, just count records
        # In future, this will:
        # 1. Apply field mappings from connector_config["field_mapping_id"]
        # 2. Transform data using ETL pipeline
        # 3. Load into target storage

        processed = 0
        failed = 0

        for record in batch:
            try:
                # TODO: Apply transformations via ETL pipeline
                # For now, records are extracted and counted
                processed += 1
            except Exception:
                failed += 1

        return processed, failed

    def _update_connector_sync_status(
        self,
        connector_id: str,
        status: str,
        watermark: str | None,
    ) -> None:
        """Update connector's last sync status.

        Args:
            connector_id: Connector ID
            status: Sync status (success, failed)
            watermark: Final watermark value
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                UPDATE connectors
                SET last_sync_at = ?, last_sync_status = ?
                WHERE id = ?
                """,
                (now, status, connector_id),
            )
            conn.commit()


# Global worker instance
_worker_instance: SyncWorker | None = None


def get_worker(db_path: str | None = None) -> SyncWorker:
    """Get or create the global worker instance.

    Args:
        db_path: Database path

    Returns:
        Global SyncWorker instance
    """
    global _worker_instance

    if _worker_instance is None:
        _worker_instance = SyncWorker(db_path=db_path)

    return _worker_instance


def execute_sync_job(
    connector_id: str,
    job_type: JobType = JobType.MANUAL,
    sync_mode: str = "incremental",
    triggered_by: str | None = None,
) -> str:
    """Execute a sync job.

    Convenience function that uses the global worker.

    Args:
        connector_id: Connector to sync
        job_type: SCHEDULED or MANUAL
        sync_mode: FULL or INCREMENTAL
        triggered_by: User or system that triggered

    Returns:
        Job ID
    """
    worker = get_worker()
    return worker.execute_sync(connector_id, job_type, sync_mode, triggered_by)
