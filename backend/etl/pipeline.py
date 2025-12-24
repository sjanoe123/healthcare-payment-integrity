"""ETL Pipeline orchestrator for data synchronization.

Coordinates extraction, transformation, and loading of data
from source connectors to target storage.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .stages.extract import ExtractStage
from .stages.transform import TransformStage
from .stages.load import LoadStage

logger = logging.getLogger(__name__)


@dataclass
class ETLContext:
    """Context for an ETL pipeline execution."""

    connector_id: str
    connector_type: str
    data_type: str
    sync_mode: str = "full"
    watermark_value: str | None = None
    mapping_id: str | None = None
    job_id: str | None = None

    # Runtime state
    started_at: str | None = None
    completed_at: str | None = None
    status: str = "pending"

    # Metrics
    total_extracted: int = 0
    total_transformed: int = 0
    total_loaded: int = 0
    total_failed: int = 0


@dataclass
class ETLResult:
    """Result from an ETL pipeline execution."""

    success: bool
    context: ETLContext
    extracted_count: int
    transformed_count: int
    loaded_count: int
    failed_count: int
    final_watermark: str | None = None
    error_message: str | None = None
    stage_results: dict[str, Any] = field(default_factory=dict)


class ETLPipeline:
    """Pipeline for orchestrating ETL operations.

    Coordinates the extract, transform, and load stages
    with progress tracking and error handling.
    """

    def __init__(
        self,
        connector: Any,
        db_path: str | None = None,
        batch_size: int = 1000,
    ) -> None:
        """Initialize the ETL pipeline.

        Args:
            connector: Source connector instance
            db_path: Target database path
            batch_size: Records per batch
        """
        self.connector = connector
        self.db_path = db_path or os.getenv("DB_PATH", "./data/prototype.db")
        self.batch_size = batch_size

        self._extract_stage: ExtractStage | None = None
        self._transform_stage: TransformStage | None = None
        self._load_stage: LoadStage | None = None

        # Callbacks
        self._on_progress: Callable[[str, int, int], None] | None = None
        self._on_error: Callable[[str, Exception], None] | None = None

    def configure(
        self,
        data_type: str,
        table_name: str | None = None,
        mapping_id: str | None = None,
        watermark_column: str | None = None,
    ) -> "ETLPipeline":
        """Configure the pipeline stages.

        Args:
            data_type: Data type (claims, eligibility, providers, reference)
            table_name: Target table name (defaults to synced_{data_type})
            mapping_id: Field mapping configuration ID
            watermark_column: Column for incremental sync

        Returns:
            Self for chaining
        """
        target_table = table_name or f"synced_{data_type}"

        self._extract_stage = ExtractStage(
            connector=self.connector,
            batch_size=self.batch_size,
            watermark_column=watermark_column,
        )

        self._transform_stage = TransformStage(
            mapping_id=mapping_id,
            data_type=data_type,
        )

        self._load_stage = LoadStage(
            db_path=self.db_path,
            table_name=target_table,
            data_type=data_type,
            batch_size=self.batch_size,
        )

        return self

    def on_progress(self, callback: Callable[[str, int, int], None]) -> "ETLPipeline":
        """Set progress callback.

        Args:
            callback: Function(stage, processed, total)

        Returns:
            Self for chaining
        """
        self._on_progress = callback
        return self

    def on_error(self, callback: Callable[[str, Exception], None]) -> "ETLPipeline":
        """Set error callback.

        Args:
            callback: Function(stage, error)

        Returns:
            Self for chaining
        """
        self._on_error = callback
        return self

    def run(
        self,
        context: ETLContext,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ETLResult:
        """Run the ETL pipeline.

        Args:
            context: Execution context
            cancel_check: Function returning True to cancel

        Returns:
            ETLResult with execution summary
        """
        if not all([self._extract_stage, self._transform_stage, self._load_stage]):
            raise RuntimeError("Pipeline not configured. Call configure() first.")

        context.started_at = datetime.now(timezone.utc).isoformat()
        context.status = "running"

        stage_results: dict[str, Any] = {
            "extract": {},
            "transform": {},
            "load": {},
        }

        total_extracted = 0
        total_transformed = 0
        total_loaded = 0
        total_failed = 0
        final_watermark = context.watermark_value

        try:
            # Connect if needed
            if not self.connector.is_connected:
                self.connector.connect()

            logger.info(f"Starting ETL pipeline for connector {context.connector_id}")

            # Process batches
            for extraction in self._extract_stage.extract(
                sync_mode=context.sync_mode,
                watermark_value=context.watermark_value,
            ):
                # Check for cancellation
                if cancel_check and cancel_check():
                    logger.info("ETL pipeline cancelled")
                    context.status = "cancelled"
                    break

                total_extracted += extraction.total_in_batch

                # Report extract progress
                if self._on_progress:
                    self._on_progress("extract", total_extracted, 0)

                # Transform batch
                transform_result = self._transform_stage.transform(
                    records=extraction.records,
                    on_error=lambda r, e: self._handle_stage_error("transform", e),
                )

                total_transformed += transform_result.transformed_count
                total_failed += transform_result.failed_count

                # Report transform progress
                if self._on_progress:
                    self._on_progress("transform", total_transformed, total_extracted)

                # Load transformed records
                if transform_result.records:
                    load_result = self._load_stage.load(
                        records=transform_result.records,
                        source_connector_id=context.connector_id,
                    )

                    total_loaded += (
                        load_result.inserted_count + load_result.updated_count
                    )
                    total_failed += load_result.failed_count

                    # Report load progress
                    if self._on_progress:
                        self._on_progress("load", total_loaded, total_transformed)

                # Update watermark
                if extraction.watermark_value:
                    final_watermark = extraction.watermark_value

            # Update context
            context.total_extracted = total_extracted
            context.total_transformed = total_transformed
            context.total_loaded = total_loaded
            context.total_failed = total_failed
            context.completed_at = datetime.now(timezone.utc).isoformat()

            if context.status != "cancelled":
                context.status = "success" if total_failed == 0 else "partial"

            logger.info(
                f"ETL pipeline completed: extracted={total_extracted}, "
                f"transformed={total_transformed}, loaded={total_loaded}, "
                f"failed={total_failed}"
            )

            return ETLResult(
                success=context.status == "success",
                context=context,
                extracted_count=total_extracted,
                transformed_count=total_transformed,
                loaded_count=total_loaded,
                failed_count=total_failed,
                final_watermark=final_watermark,
                stage_results=stage_results,
            )

        except Exception as e:
            error_msg = str(e)
            logger.exception(f"ETL pipeline failed: {error_msg}")

            context.status = "failed"
            context.completed_at = datetime.now(timezone.utc).isoformat()

            if self._on_error:
                self._on_error("pipeline", e)

            return ETLResult(
                success=False,
                context=context,
                extracted_count=total_extracted,
                transformed_count=total_transformed,
                loaded_count=total_loaded,
                failed_count=total_failed,
                final_watermark=final_watermark,
                error_message=error_msg,
                stage_results=stage_results,
            )

        finally:
            # Disconnect
            try:
                self.connector.disconnect()
            except Exception:
                pass

    def _handle_stage_error(self, stage: str, error: Exception) -> None:
        """Handle errors from a stage.

        Args:
            stage: Stage name
            error: The exception
        """
        logger.warning(f"Error in {stage} stage: {error}")
        if self._on_error:
            self._on_error(stage, error)

    def get_source_schema(self) -> dict[str, Any]:
        """Get schema from the source connector.

        Returns:
            Schema information
        """
        if self._extract_stage:
            return self._extract_stage.get_schema()
        return {}

    def get_target_record_count(self) -> int:
        """Get current record count in target.

        Returns:
            Number of records
        """
        if self._load_stage:
            return self._load_stage.get_record_count()
        return 0


def create_pipeline(
    connector: Any,
    data_type: str,
    db_path: str | None = None,
    table_name: str | None = None,
    mapping_id: str | None = None,
    watermark_column: str | None = None,
    batch_size: int = 1000,
) -> ETLPipeline:
    """Create and configure an ETL pipeline.

    Args:
        connector: Source connector instance
        data_type: Data type (claims, eligibility, providers, reference)
        db_path: Target database path
        table_name: Target table name
        mapping_id: Field mapping configuration ID
        watermark_column: Column for incremental sync
        batch_size: Records per batch

    Returns:
        Configured ETLPipeline
    """
    pipeline = ETLPipeline(
        connector=connector,
        db_path=db_path,
        batch_size=batch_size,
    )

    pipeline.configure(
        data_type=data_type,
        table_name=table_name,
        mapping_id=mapping_id,
        watermark_column=watermark_column,
    )

    return pipeline
