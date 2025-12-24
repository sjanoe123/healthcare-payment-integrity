"""Extract stage for ETL pipeline.

Handles data extraction from source connectors including:
- Batch processing with configurable sizes
- Watermark-based incremental extraction
- Progress tracking and logging
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterator

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result from an extraction operation."""

    records: list[dict[str, Any]]
    batch_number: int
    total_in_batch: int
    watermark_value: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ExtractStage:
    """Extract stage for pulling data from source connectors.

    Handles batch extraction with progress tracking and
    watermark management for incremental syncs.
    """

    def __init__(
        self,
        connector: Any,
        batch_size: int = 1000,
        watermark_column: str | None = None,
    ) -> None:
        """Initialize the extract stage.

        Args:
            connector: Source connector instance
            batch_size: Records per batch
            watermark_column: Column for incremental sync tracking
        """
        self.connector = connector
        self.batch_size = batch_size
        self.watermark_column = watermark_column

    def extract(
        self,
        sync_mode: str = "full",
        watermark_value: str | None = None,
        on_progress: Any | None = None,
    ) -> Iterator[ExtractionResult]:
        """Extract data from the source connector.

        Args:
            sync_mode: "full" or "incremental"
            watermark_value: Starting watermark for incremental
            on_progress: Optional callback for progress updates

        Yields:
            ExtractionResult for each batch
        """
        from ...connectors.models import SyncMode

        mode = SyncMode.INCREMENTAL if sync_mode == "incremental" else SyncMode.FULL

        # Ensure connected
        if not self.connector._connected:
            self.connector.connect()

        batch_number = 0
        total_extracted = 0

        try:
            for batch in self.connector.extract(mode, watermark_value):
                batch_number += 1
                batch_size = len(batch)
                total_extracted += batch_size

                # Get watermark from last record
                current_watermark = None
                if self.watermark_column and batch:
                    last_record = batch[-1]
                    if self.watermark_column in last_record:
                        current_watermark = str(last_record[self.watermark_column])

                result = ExtractionResult(
                    records=batch,
                    batch_number=batch_number,
                    total_in_batch=batch_size,
                    watermark_value=current_watermark,
                    metadata={
                        "total_extracted": total_extracted,
                        "sync_mode": sync_mode,
                    },
                )

                # Progress callback
                if on_progress:
                    on_progress(
                        batch_number=batch_number,
                        records_in_batch=batch_size,
                        total_extracted=total_extracted,
                    )

                logger.debug(
                    f"Extracted batch {batch_number}: {batch_size} records, "
                    f"total: {total_extracted}"
                )

                yield result

        finally:
            logger.info(
                f"Extraction complete: {batch_number} batches, {total_extracted} records"
            )

    def count_source_records(self, table: str | None = None) -> int:
        """Count total records in source.

        Args:
            table: Optional table name

        Returns:
            Record count
        """
        if hasattr(self.connector, "get_row_count"):
            return self.connector.get_row_count(table)
        return 0

    def get_schema(self) -> dict[str, Any]:
        """Get source schema information.

        Returns:
            Schema discovery result
        """
        if hasattr(self.connector, "discover_schema"):
            result = self.connector.discover_schema()
            return {
                "tables": result.tables,
                "columns": result.columns,
            }
        return {}
