"""AWS S3 connector for file-based data extraction.

Provides connectivity to S3 buckets for extracting healthcare data
files including EDI 837 claims and CSV exports.
"""

from __future__ import annotations

import fnmatch
import logging
import time
from typing import Any

from ..models import ConnectionTestResult, ConnectorSubtype, ConnectorType, DataType
from ..registry import register_connector
from .base_file import BaseFileConnector, FileConnectionError, FileInfo

logger = logging.getLogger(__name__)

# Try to import boto3
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None  # type: ignore
    BotoCoreError = Exception  # type: ignore
    ClientError = Exception  # type: ignore
    logger.warning("boto3 not installed - S3 connector disabled")


class S3Connector(BaseFileConnector):
    """Connector for AWS S3 buckets.

    Supports:
    - IAM role or access key authentication
    - Custom endpoints (for S3-compatible services)
    - Path pattern matching
    - File archiving after processing
    """

    def __init__(
        self,
        connector_id: str,
        name: str,
        config: dict[str, Any],
        batch_size: int = 1000,
    ) -> None:
        """Initialize S3 connector.

        Args:
            connector_id: Unique identifier
            name: Human-readable name
            config: S3 configuration with keys:
                - bucket: S3 bucket name
                - region: AWS region
                - access_key_id: AWS access key (optional if using IAM role)
                - secret_access_key: AWS secret key (optional)
                - endpoint_url: Custom endpoint (for S3-compatible services)
                - prefix: Path prefix to filter files
                - path_pattern: Glob pattern for files
                - file_format: edi_837, csv, json
            batch_size: Records per batch
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 is required. Install with: pip install boto3")

        super().__init__(connector_id, name, config, batch_size)
        self._client: Any = None

    def connect(self) -> None:
        """Establish connection to S3."""
        if self._connected:
            return

        try:
            # Build client kwargs
            client_kwargs: dict[str, Any] = {
                "service_name": "s3",
            }

            # Region
            if self.config.get("region"):
                client_kwargs["region_name"] = self.config["region"]

            # Credentials (optional - can use IAM role)
            if self.config.get("access_key_id") and self.config.get(
                "secret_access_key"
            ):
                client_kwargs["aws_access_key_id"] = self.config["access_key_id"]
                client_kwargs["aws_secret_access_key"] = self.config[
                    "secret_access_key"
                ]

            # Custom endpoint (for S3-compatible services like MinIO)
            if self.config.get("endpoint_url"):
                client_kwargs["endpoint_url"] = self.config["endpoint_url"]

            self._client = boto3.client(**client_kwargs)

            # Verify bucket access
            bucket = self.config.get("bucket")
            if not bucket:
                raise ValueError("Bucket name is required")

            self._client.head_bucket(Bucket=bucket)

            self._connected = True
            self._log("info", f"Connected to S3 bucket: {bucket}")

        except (BotoCoreError, ClientError) as e:
            raise FileConnectionError(
                f"Failed to connect to S3: {e}", self.connector_id
            ) from e

    def disconnect(self) -> None:
        """Disconnect from S3."""
        self._client = None
        super().disconnect()

    def test_connection(self) -> ConnectionTestResult:
        """Test S3 connection."""
        start_time = time.time()

        try:
            # Build client
            client_kwargs: dict[str, Any] = {"service_name": "s3"}

            if self.config.get("region"):
                client_kwargs["region_name"] = self.config["region"]

            if self.config.get("access_key_id") and self.config.get(
                "secret_access_key"
            ):
                client_kwargs["aws_access_key_id"] = self.config["access_key_id"]
                client_kwargs["aws_secret_access_key"] = self.config[
                    "secret_access_key"
                ]

            if self.config.get("endpoint_url"):
                client_kwargs["endpoint_url"] = self.config["endpoint_url"]

            client = boto3.client(**client_kwargs)

            bucket = self.config.get("bucket")
            if not bucket:
                return ConnectionTestResult(
                    success=False,
                    message="Bucket name is required",
                    latency_ms=None,
                    details={},
                )

            # Test bucket access
            client.head_bucket(Bucket=bucket)

            # List some objects
            prefix = self.config.get("prefix", "")
            response = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=10)

            latency_ms = (time.time() - start_time) * 1000

            object_count = response.get("KeyCount", 0)
            sample_files = [obj["Key"] for obj in response.get("Contents", [])[:5]]

            return ConnectionTestResult(
                success=True,
                message=f"Successfully connected to bucket: {bucket}",
                latency_ms=round(latency_ms, 2),
                details={
                    "bucket": bucket,
                    "region": self.config.get("region"),
                    "prefix": prefix,
                    "objects_found": object_count,
                    "sample_files": sample_files,
                },
            )

        except ClientError as e:
            latency_ms = (time.time() - start_time) * 1000
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            return ConnectionTestResult(
                success=False,
                message=f"S3 error ({error_code}): {str(e)[:200]}",
                latency_ms=round(latency_ms, 2),
                details={"error_code": error_code},
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Connection failed: {str(e)[:200]}",
                latency_ms=None,
                details={"error_type": type(e).__name__},
            )

    def _list_files(self, pattern: str) -> list[FileInfo]:
        """List files in S3 matching the pattern.

        Args:
            pattern: Glob pattern for matching files

        Returns:
            List of FileInfo objects
        """
        if not self._client:
            self.connect()

        bucket = self.config.get("bucket")
        prefix = self.config.get("prefix", "")

        files = []
        paginator = self._client.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    filename = key.split("/")[-1]

                    # Apply pattern matching
                    if pattern and not fnmatch.fnmatch(filename, pattern):
                        continue

                    # Skip directories
                    if key.endswith("/"):
                        continue

                    modified_at = obj.get("LastModified")
                    if modified_at and modified_at.tzinfo:
                        modified_at = modified_at.replace(tzinfo=None)

                    files.append(
                        FileInfo(
                            name=filename,
                            path=key,
                            size=obj.get("Size", 0),
                            modified_at=modified_at,
                            is_directory=False,
                        )
                    )

        except ClientError as e:
            logger.error(f"Error listing S3 objects: {e}")
            raise FileConnectionError(f"Failed to list files: {e}", self.connector_id)

        return files

    def _download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from S3.

        Args:
            remote_path: S3 object key
            local_path: Local destination path

        Returns:
            True if successful
        """
        if not self._client:
            self.connect()

        bucket = self.config.get("bucket")

        try:
            self._client.download_file(bucket, remote_path, local_path)
            return True
        except ClientError as e:
            logger.error(f"Error downloading {remote_path}: {e}")
            return False

    def _archive_file(self, source_path: str, archive_path: str) -> bool:
        """Move a file to archive location in S3.

        Args:
            source_path: Source S3 key
            archive_path: Destination S3 key

        Returns:
            True if successful
        """
        if not self._client:
            self.connect()

        bucket = self.config.get("bucket")

        try:
            # Copy to archive
            self._client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": source_path},
                Key=archive_path,
            )

            # Delete original
            self._client.delete_object(Bucket=bucket, Key=source_path)

            return True
        except ClientError as e:
            logger.error(f"Error archiving {source_path}: {e}")
            return False


# Configuration schema for the UI
S3_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["bucket"],
    "properties": {
        "bucket": {
            "type": "string",
            "title": "Bucket Name",
            "description": "S3 bucket name",
        },
        "region": {
            "type": "string",
            "title": "AWS Region",
            "description": "AWS region (e.g., us-east-1)",
            "default": "us-east-1",
        },
        "access_key_id": {
            "type": "string",
            "title": "Access Key ID",
            "description": "AWS access key (leave empty for IAM role)",
        },
        "secret_access_key": {
            "type": "string",
            "title": "Secret Access Key",
            "description": "AWS secret key",
            "format": "password",
        },
        "endpoint_url": {
            "type": "string",
            "title": "Custom Endpoint",
            "description": "Custom S3 endpoint URL (for S3-compatible services)",
        },
        "prefix": {
            "type": "string",
            "title": "Path Prefix",
            "description": "Filter files by path prefix",
            "default": "",
        },
        "path_pattern": {
            "type": "string",
            "title": "File Pattern",
            "description": "Glob pattern for files (e.g., *.edi, claims_*.csv)",
            "default": "*",
        },
        "file_format": {
            "type": "string",
            "title": "File Format",
            "description": "Format of files to parse",
            "enum": ["edi_837", "edi_837p", "edi_837i", "csv", "json"],
            "default": "csv",
        },
        "delimiter": {
            "type": "string",
            "title": "CSV Delimiter",
            "description": "Delimiter for CSV files",
            "default": ",",
        },
        "has_header": {
            "type": "boolean",
            "title": "Has Header Row",
            "description": "CSV files have header row",
            "default": True,
        },
        "archive_processed": {
            "type": "boolean",
            "title": "Archive Processed Files",
            "description": "Move files after processing",
            "default": False,
        },
        "archive_path": {
            "type": "string",
            "title": "Archive Path",
            "description": "Destination prefix for archived files",
        },
    },
}


def _register_s3() -> None:
    """Register S3 connector with the registry."""
    if not BOTO3_AVAILABLE:
        return

    register_connector(
        subtype=ConnectorSubtype.S3,
        connector_class=S3Connector,
        name="Amazon S3",
        description="Connect to AWS S3 buckets for claims files (EDI, CSV)",
        connector_type=ConnectorType.FILE,
        config_schema=S3_CONFIG_SCHEMA,
        supported_data_types=[
            DataType.CLAIMS,
            DataType.ELIGIBILITY,
            DataType.PROVIDERS,
            DataType.REFERENCE,
        ],
    )


# Auto-register on import
_register_s3()
