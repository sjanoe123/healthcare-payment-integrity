"""APScheduler wrapper for managing sync job schedules.

Provides a high-level interface for scheduling sync jobs with cron
expressions and managing the scheduler lifecycle.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Try to import APScheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None  # type: ignore
    CronTrigger = None  # type: ignore
    logger.warning("APScheduler not installed - scheduling disabled")


class SyncScheduler:
    """Scheduler for managing sync job schedules.

    Uses APScheduler with SQLite job store for persistence.
    Jobs survive application restarts.
    """

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize the scheduler.

        Args:
            db_path: Path to SQLite database for job storage
        """
        if not APSCHEDULER_AVAILABLE:
            raise ImportError(
                "APScheduler is required. Install with: pip install apscheduler"
            )

        self.db_path = db_path or os.getenv("DB_PATH", "./data/prototype.db")
        self._scheduler: BackgroundScheduler | None = None
        self._started = False

    def _create_scheduler(self) -> BackgroundScheduler:
        """Create and configure the APScheduler instance."""
        # Job stores - use SQLite for persistence
        jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite:///{self.db_path}")}

        # Executors - thread pool for sync jobs
        executors = {
            "default": ThreadPoolExecutor(max_workers=5),
        }

        # Job defaults
        job_defaults = {
            "coalesce": True,  # Combine missed runs into one
            "max_instances": 1,  # Only one instance per job
            "misfire_grace_time": 3600,  # 1 hour grace time for missed jobs
        }

        scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="UTC",
        )

        return scheduler

    def start(self) -> None:
        """Start the scheduler."""
        if self._started:
            logger.warning("Scheduler already started")
            return

        self._scheduler = self._create_scheduler()
        self._scheduler.start()
        self._started = True
        logger.info("Scheduler started")

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the scheduler.

        Args:
            wait: Whether to wait for running jobs to complete
        """
        if self._scheduler and self._started:
            self._scheduler.shutdown(wait=wait)
            self._started = False
            logger.info("Scheduler shutdown")

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._started and self._scheduler is not None

    def add_job(
        self,
        job_id: str,
        func: Callable[..., Any],
        cron_expression: str,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
        replace_existing: bool = True,
    ) -> None:
        """Add a scheduled job.

        Args:
            job_id: Unique identifier for the job
            func: Function to execute
            cron_expression: Cron schedule (e.g., "0 */6 * * *")
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            replace_existing: Replace if job already exists
        """
        if not self._scheduler:
            raise RuntimeError("Scheduler not started")

        # Parse cron expression
        trigger = self._parse_cron(cron_expression)

        self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            args=args or (),
            kwargs=kwargs or {},
            replace_existing=replace_existing,
        )
        logger.info(f"Added scheduled job: {job_id} with schedule: {cron_expression}")

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job.

        Args:
            job_id: Job identifier to remove

        Returns:
            True if job was removed, False if not found
        """
        if not self._scheduler:
            return False

        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job: {job_id}")
            return True
        except Exception:
            return False

    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job.

        Args:
            job_id: Job identifier to pause

        Returns:
            True if job was paused
        """
        if not self._scheduler:
            return False

        try:
            self._scheduler.pause_job(job_id)
            logger.info(f"Paused job: {job_id}")
            return True
        except Exception:
            return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job.

        Args:
            job_id: Job identifier to resume

        Returns:
            True if job was resumed
        """
        if not self._scheduler:
            return False

        try:
            self._scheduler.resume_job(job_id)
            logger.info(f"Resumed job: {job_id}")
            return True
        except Exception:
            return False

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job details.

        Args:
            job_id: Job identifier

        Returns:
            Job details dict or None
        """
        if not self._scheduler:
            return None

        job = self._scheduler.get_job(job_id)
        if not job:
            return None

        return {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat()
            if job.next_run_time
            else None,
            "trigger": str(job.trigger),
        }

    def get_jobs(self) -> list[dict[str, Any]]:
        """Get all scheduled jobs.

        Returns:
            List of job details
        """
        if not self._scheduler:
            return []

        jobs = self._scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat()
                if job.next_run_time
                else None,
                "trigger": str(job.trigger),
            }
            for job in jobs
        ]

    def run_job_now(self, job_id: str) -> bool:
        """Trigger immediate execution of a scheduled job.

        Args:
            job_id: Job identifier

        Returns:
            True if job was triggered
        """
        if not self._scheduler:
            return False

        job = self._scheduler.get_job(job_id)
        if not job:
            return False

        # Modify job to run immediately (next second)
        job.modify(next_run_time=None)
        self._scheduler.modify_job(job_id, next_run_time=None)
        return True

    def _parse_cron(self, cron_expression: str) -> CronTrigger:
        """Parse a cron expression into an APScheduler trigger.

        Args:
            cron_expression: Standard cron format (minute hour day month day_of_week)

        Returns:
            CronTrigger instance
        """
        parts = cron_expression.strip().split()

        if len(parts) == 5:
            # Standard cron: minute hour day month day_of_week
            return CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        elif len(parts) == 6:
            # Extended cron with seconds
            return CronTrigger(
                second=parts[0],
                minute=parts[1],
                hour=parts[2],
                day=parts[3],
                month=parts[4],
                day_of_week=parts[5],
            )
        else:
            raise ValueError(
                f"Invalid cron expression: {cron_expression}. "
                "Expected 5 or 6 space-separated fields."
            )


# Global scheduler instance
_scheduler_instance: SyncScheduler | None = None


def get_scheduler(db_path: str | None = None) -> SyncScheduler:
    """Get or create the global scheduler instance.

    Args:
        db_path: Database path (only used on first call)

    Returns:
        Global SyncScheduler instance
    """
    global _scheduler_instance

    if _scheduler_instance is None:
        _scheduler_instance = SyncScheduler(db_path)

    return _scheduler_instance


def start_scheduler(db_path: str | None = None) -> SyncScheduler:
    """Start the global scheduler.

    Args:
        db_path: Database path

    Returns:
        Started scheduler instance
    """
    scheduler = get_scheduler(db_path)
    if not scheduler.is_running:
        scheduler.start()
    return scheduler


def shutdown_scheduler(wait: bool = True) -> None:
    """Shutdown the global scheduler.

    Args:
        wait: Whether to wait for running jobs
    """
    global _scheduler_instance

    if _scheduler_instance:
        _scheduler_instance.shutdown(wait=wait)
        _scheduler_instance = None
