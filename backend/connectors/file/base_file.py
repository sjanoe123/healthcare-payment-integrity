"""Base file connector for file-based data sources.

Provides common functionality for all file connectors including:
- File listing and filtering
- File download and parsing
- Batch processing with progress tracking
"""

from __future__ import annotations

import logging
import os
import tempfile
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator

from ..base import BaseConnector, ConnectorError
from ..models import SchemaDiscoveryResult, SyncMode

logger = logging.getLogger(__name__)


class FileConnectionError(ConnectorError):
    """Error connecting to a file source."""

    pass


@dataclass
class FileInfo:
    """Information about a remote file."""

    name: str
    path: str
    size: int
    modified_at: datetime | None = None
    is_directory: bool = False


class BaseFileConnector(BaseConnector):
    """Base class for file-based connectors.

    Provides common functionality for:
    - File listing with glob patterns
    - File download to local temp directory
    - Parsing with pluggable parsers
    - Batch processing

    Subclasses must implement:
    - connect(): Establish connection to file source
    - disconnect(): Close connection
    - _list_files(): List files matching pattern
    - _download_file(): Download file to local path
    """

    def __init__(
        self,
        connector_id: str,
        name: str,
        config: dict[str, Any],
        batch_size: int = 1000,
    ) -> None:
        """Initialize the file connector.

        Args:
            connector_id: Unique identifier
            name: Human-readable name
            config: File source configuration with keys:
                - path_pattern: Glob pattern for files (e.g., "claims/*.edi")
                - file_format: Format type (edi_837, csv, json)
                - archive_processed: Move processed files (optional)
                - archive_path: Archive destination (optional)
            batch_size: Records per batch
        """
        super().__init__(connector_id, name, config, batch_size)
        self._temp_dir: str | None = None
        self._parser: Any = None

    @abstractmethod
    def _list_files(self, pattern: str) -> list[FileInfo]:
        """List files matching the pattern.

        Args:
            pattern: Glob pattern

        Returns:
            List of FileInfo objects
        """
        pass

    @abstractmethod
    def _download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file to local path.

        Args:
            remote_path: Remote file path
            local_path: Local destination path

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def _archive_file(self, source_path: str, archive_path: str) -> bool:
        """Move a file to archive location.

        Args:
            source_path: Source file path
            archive_path: Archive destination

        Returns:
            True if successful
        """
        pass

    def _get_parser(self) -> Any:
        """Get the appropriate parser for the file format.

        Returns:
            Parser instance
        """
        if self._parser:
            return self._parser

        file_format = self.config.get("file_format", "csv")

        if (
            file_format == "edi_837"
            or file_format == "edi_837p"
            or file_format == "edi_837i"
        ):
            from .parsers.edi_837 import EDI837Parser

            self._parser = EDI837Parser()
        elif file_format == "csv":
            from .parsers.csv_parser import CSVParser

            delimiter = self.config.get("delimiter", ",")
            has_header = self.config.get("has_header", True)
            self._parser = CSVParser(delimiter=delimiter, has_header=has_header)
        elif file_format == "json":
            from .parsers.csv_parser import JSONParser

            self._parser = JSONParser()
        else:
            raise ValueError(f"Unsupported file format: {file_format}")

        return self._parser

    def _get_temp_dir(self) -> str:
        """Get or create temporary directory for downloads.

        Returns:
            Path to temp directory
        """
        if not self._temp_dir:
            self._temp_dir = tempfile.mkdtemp(prefix="connector_")
        return self._temp_dir

    def _cleanup_temp_dir(self) -> None:
        """Clean up temporary directory."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            import shutil

            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def discover_schema(self) -> SchemaDiscoveryResult:
        """Discover schema from sample files.

        Returns:
            SchemaDiscoveryResult with file info and sample data
        """
        if not self._connected:
            self.connect()

        pattern = self.config.get("path_pattern", "*")
        files = self._list_files(pattern)

        if not files:
            return SchemaDiscoveryResult(
                tables=[],
                columns={},
                sample_data={},
            )

        # Use first file as sample
        sample_file = files[0]
        temp_dir = self._get_temp_dir()
        local_path = os.path.join(temp_dir, os.path.basename(sample_file.name))

        try:
            self._download_file(sample_file.path, local_path)
            parser = self._get_parser()
            records = list(parser.parse(local_path, limit=10))

            # Extract columns from first record
            columns = {}
            if records:
                first_record = records[0]
                columns["records"] = [
                    {"name": key, "type": type(value).__name__, "nullable": True}
                    for key, value in first_record.items()
                ]

            return SchemaDiscoveryResult(
                tables=[f.name for f in files[:20]],  # Show first 20 files
                columns=columns,
                sample_data={"records": records[:3]},
            )

        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    def extract(
        self,
        sync_mode: SyncMode,
        watermark_value: str | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        """Extract data from files in batches.

        Args:
            sync_mode: FULL or INCREMENTAL
            watermark_value: Last processed file timestamp (for incremental)

        Yields:
            Batches of records
        """
        if not self._connected:
            self.connect()

        pattern = self.config.get("path_pattern", "*")
        files = self._list_files(pattern)

        # Filter for incremental sync
        if sync_mode == SyncMode.INCREMENTAL and watermark_value:
            try:
                watermark_dt = datetime.fromisoformat(watermark_value)
                files = [
                    f for f in files if f.modified_at and f.modified_at > watermark_dt
                ]
            except ValueError:
                logger.warning(f"Invalid watermark format: {watermark_value}")

        # Sort by modification time
        files.sort(key=lambda f: f.modified_at or datetime.min)

        parser = self._get_parser()
        temp_dir = self._get_temp_dir()
        archive_path = self.config.get("archive_path")
        archive_processed = self.config.get("archive_processed", False)

        try:
            for file_info in files:
                local_path = os.path.join(temp_dir, os.path.basename(file_info.name))

                try:
                    # Download file
                    if not self._download_file(file_info.path, local_path):
                        logger.warning(f"Failed to download: {file_info.path}")
                        continue

                    # Parse and yield batches
                    batch: list[dict[str, Any]] = []

                    for record in parser.parse(local_path):
                        # Add file metadata
                        record["_source_file"] = file_info.name
                        record["_file_modified_at"] = (
                            file_info.modified_at.isoformat()
                            if file_info.modified_at
                            else None
                        )

                        batch.append(record)

                        if len(batch) >= self.batch_size:
                            yield batch
                            batch = []

                    # Yield remaining
                    if batch:
                        yield batch

                    # Archive if configured
                    if archive_processed and archive_path:
                        dest = os.path.join(archive_path, file_info.name)
                        self._archive_file(file_info.path, dest)

                finally:
                    # Clean up local file
                    if os.path.exists(local_path):
                        os.remove(local_path)

        finally:
            self._cleanup_temp_dir()

    def get_current_watermark(self) -> str | None:
        """Get the current watermark (latest file timestamp).

        Returns:
            ISO timestamp of newest file or None
        """
        if not self._connected:
            self.connect()

        pattern = self.config.get("path_pattern", "*")
        files = self._list_files(pattern)

        if not files:
            return None

        # Find newest file
        newest = max(
            (f for f in files if f.modified_at),
            key=lambda f: f.modified_at or datetime.min,
            default=None,
        )

        if newest and newest.modified_at:
            return newest.modified_at.isoformat()

        return None

    def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        self._cleanup_temp_dir()
        self._connected = False
        self._log("info", "Disconnected")
