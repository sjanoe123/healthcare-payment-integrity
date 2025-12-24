"""Azure Blob Storage connector for file-based data extraction.

Provides connectivity to Azure Blob Storage containers for extracting
healthcare data files including EDI 837 claims and CSV exports.
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

# Try to import azure-storage-blob
try:
    from azure.core.exceptions import AzureError
    from azure.storage.blob import BlobServiceClient, ContainerClient

    AZURE_BLOB_AVAILABLE = True
except ImportError:
    AZURE_BLOB_AVAILABLE = False
    AzureError = Exception  # type: ignore
    BlobServiceClient = Any  # type: ignore
    ContainerClient = Any  # type: ignore
    logger.warning("azure-storage-blob not installed - Azure Blob connector disabled")


class AzureBlobConnector(BaseFileConnector):
    """Connector for Azure Blob Storage.

    Supports:
    - Connection string authentication
    - Account key authentication
    - SAS token authentication
    - Azure AD (Managed Identity) authentication
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
        """Initialize Azure Blob connector.

        Args:
            connector_id: Unique identifier
            name: Human-readable name
            config: Azure Blob configuration with keys:
                - account_name: Storage account name
                - container_name: Container name
                - connection_string: Full connection string (optional)
                - account_key: Account access key (optional)
                - sas_token: SAS token (optional)
                - prefix: Path prefix to filter blobs
                - path_pattern: Glob pattern for files
                - file_format: edi_837, csv, json
            batch_size: Records per batch
        """
        if not AZURE_BLOB_AVAILABLE:
            raise ImportError(
                "azure-storage-blob is required. "
                "Install with: pip install azure-storage-blob"
            )

        super().__init__(connector_id, name, config, batch_size)
        self._blob_service: BlobServiceClient | None = None
        self._container_client: ContainerClient | None = None

    def connect(self) -> None:
        """Establish connection to Azure Blob Storage."""
        if self._connected:
            return

        try:
            container_name = self.config.get("container_name")
            if not container_name:
                raise ValueError("Container name is required")

            # Try different authentication methods
            connection_string = self.config.get("connection_string")
            account_name = self.config.get("account_name")
            account_key = self.config.get("account_key")
            sas_token = self.config.get("sas_token")

            if connection_string:
                # Use connection string
                self._blob_service = BlobServiceClient.from_connection_string(
                    connection_string
                )
            elif account_name and account_key:
                # Use account key
                account_url = f"https://{account_name}.blob.core.windows.net"
                self._blob_service = BlobServiceClient(
                    account_url=account_url,
                    credential=account_key,
                )
            elif account_name and sas_token:
                # Use SAS token
                account_url = f"https://{account_name}.blob.core.windows.net"
                # Ensure SAS token starts with ?
                if not sas_token.startswith("?"):
                    sas_token = "?" + sas_token
                self._blob_service = BlobServiceClient(
                    account_url=account_url + sas_token
                )
            elif account_name:
                # Use DefaultAzureCredential (Managed Identity, CLI, etc.)
                try:
                    from azure.identity import DefaultAzureCredential

                    account_url = f"https://{account_name}.blob.core.windows.net"
                    credential = DefaultAzureCredential()
                    self._blob_service = BlobServiceClient(
                        account_url=account_url,
                        credential=credential,
                    )
                except ImportError:
                    raise ValueError(
                        "azure-identity is required for DefaultAzureCredential. "
                        "Install with: pip install azure-identity"
                    )
            else:
                raise ValueError(
                    "Either connection_string, account_key, or sas_token is required"
                )

            # Get container client and verify access
            self._container_client = self._blob_service.get_container_client(
                container_name
            )

            # Test container access
            self._container_client.get_container_properties()

            self._connected = True
            self._log("info", f"Connected to Azure Blob container: {container_name}")

        except AzureError as e:
            raise FileConnectionError(
                f"Failed to connect to Azure Blob: {e}", self.connector_id
            ) from e
        except Exception as e:
            raise FileConnectionError(
                f"Connection error: {e}", self.connector_id
            ) from e

    def disconnect(self) -> None:
        """Disconnect from Azure Blob Storage."""
        self._container_client = None
        self._blob_service = None
        super().disconnect()

    def test_connection(self) -> ConnectionTestResult:
        """Test Azure Blob Storage connection."""
        start_time = time.time()

        try:
            container_name = self.config.get("container_name")
            if not container_name:
                return ConnectionTestResult(
                    success=False,
                    message="Container name is required",
                    latency_ms=None,
                    details={},
                )

            # Build service client
            connection_string = self.config.get("connection_string")
            account_name = self.config.get("account_name")
            account_key = self.config.get("account_key")
            sas_token = self.config.get("sas_token")

            if connection_string:
                blob_service = BlobServiceClient.from_connection_string(
                    connection_string
                )
            elif account_name and account_key:
                account_url = f"https://{account_name}.blob.core.windows.net"
                blob_service = BlobServiceClient(
                    account_url=account_url,
                    credential=account_key,
                )
            elif account_name and sas_token:
                account_url = f"https://{account_name}.blob.core.windows.net"
                if not sas_token.startswith("?"):
                    sas_token = "?" + sas_token
                blob_service = BlobServiceClient(account_url=account_url + sas_token)
            elif account_name:
                try:
                    from azure.identity import DefaultAzureCredential

                    account_url = f"https://{account_name}.blob.core.windows.net"
                    credential = DefaultAzureCredential()
                    blob_service = BlobServiceClient(
                        account_url=account_url,
                        credential=credential,
                    )
                except ImportError:
                    return ConnectionTestResult(
                        success=False,
                        message="azure-identity required for DefaultAzureCredential",
                        latency_ms=None,
                        details={},
                    )
            else:
                return ConnectionTestResult(
                    success=False,
                    message="No valid credentials provided",
                    latency_ms=None,
                    details={},
                )

            # Test container access
            container_client = blob_service.get_container_client(container_name)
            container_props = container_client.get_container_properties()

            # List some blobs
            prefix = self.config.get("prefix", "")
            blobs = list(
                container_client.list_blobs(
                    name_starts_with=prefix, results_per_page=10
                )
            )

            latency_ms = (time.time() - start_time) * 1000

            sample_files = [blob.name for blob in blobs[:5]]

            return ConnectionTestResult(
                success=True,
                message=f"Successfully connected to container: {container_name}",
                latency_ms=round(latency_ms, 2),
                details={
                    "container": container_name,
                    "account": account_name or "(from connection string)",
                    "prefix": prefix,
                    "blobs_found": len(blobs),
                    "sample_files": sample_files,
                    "last_modified": (
                        container_props.last_modified.isoformat()
                        if container_props.last_modified
                        else None
                    ),
                },
            )

        except AzureError as e:
            latency_ms = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                success=False,
                message=f"Azure Blob error: {str(e)[:200]}",
                latency_ms=round(latency_ms, 2),
                details={"error_type": type(e).__name__},
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Connection failed: {str(e)[:200]}",
                latency_ms=None,
                details={"error_type": type(e).__name__},
            )

    def _list_files(self, pattern: str) -> list[FileInfo]:
        """List blobs in Azure container matching the pattern.

        Args:
            pattern: Glob pattern for matching files

        Returns:
            List of FileInfo objects
        """
        if not self._container_client:
            self.connect()

        assert self._container_client is not None

        prefix = self.config.get("prefix", "")
        files = []

        try:
            blobs = self._container_client.list_blobs(name_starts_with=prefix)

            for blob in blobs:
                filename = blob.name.split("/")[-1]

                # Apply pattern matching
                if pattern and not fnmatch.fnmatch(filename, pattern):
                    continue

                # Skip directories (blobs ending with /)
                if blob.name.endswith("/"):
                    continue

                modified_at = blob.last_modified
                if modified_at and hasattr(modified_at, "replace"):
                    # Remove timezone info for consistency
                    modified_at = modified_at.replace(tzinfo=None)

                files.append(
                    FileInfo(
                        name=filename,
                        path=blob.name,
                        size=blob.size or 0,
                        modified_at=modified_at,
                        is_directory=False,
                    )
                )

        except AzureError as e:
            logger.error(f"Error listing Azure blobs: {e}")
            raise FileConnectionError(f"Failed to list blobs: {e}", self.connector_id)

        return files

    def _download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a blob from Azure storage.

        Args:
            remote_path: Blob name/path
            local_path: Local destination path

        Returns:
            True if successful
        """
        if not self._container_client:
            self.connect()

        assert self._container_client is not None

        try:
            blob_client = self._container_client.get_blob_client(remote_path)

            with open(local_path, "wb") as file:
                download_stream = blob_client.download_blob()
                file.write(download_stream.readall())

            return True

        except AzureError as e:
            logger.error(f"Error downloading blob {remote_path}: {e}")
            return False

    def _archive_file(self, source_path: str, archive_path: str) -> bool:
        """Move a blob to archive location.

        Args:
            source_path: Source blob path
            archive_path: Destination blob path

        Returns:
            True if successful
        """
        if not self._container_client:
            self.connect()

        assert self._container_client is not None

        try:
            # Get source and destination blob clients
            source_blob = self._container_client.get_blob_client(source_path)
            dest_blob = self._container_client.get_blob_client(archive_path)

            # Copy blob to archive
            dest_blob.start_copy_from_url(source_blob.url)

            # Wait for copy to complete (simplified - in production use polling)
            import time

            time.sleep(1)

            # Delete source
            source_blob.delete_blob()

            return True

        except AzureError as e:
            logger.error(f"Error archiving blob {source_path}: {e}")
            return False


# Configuration schema for the UI
AZURE_BLOB_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["container_name"],
    "properties": {
        "container_name": {
            "type": "string",
            "title": "Container Name",
            "description": "Azure Blob Storage container name",
        },
        "account_name": {
            "type": "string",
            "title": "Storage Account",
            "description": "Azure Storage account name",
        },
        "connection_string": {
            "type": "string",
            "title": "Connection String",
            "description": "Full connection string (overrides other auth options)",
            "format": "password",
        },
        "account_key": {
            "type": "string",
            "title": "Account Key",
            "description": "Storage account access key",
            "format": "password",
        },
        "sas_token": {
            "type": "string",
            "title": "SAS Token",
            "description": "Shared Access Signature token",
            "format": "password",
        },
        "prefix": {
            "type": "string",
            "title": "Path Prefix",
            "description": "Filter blobs by path prefix (virtual folder)",
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
            "description": "Move files to archive after processing",
            "default": False,
        },
        "archive_path": {
            "type": "string",
            "title": "Archive Path",
            "description": "Destination prefix for archived files",
        },
    },
}


def _register_azure_blob() -> None:
    """Register Azure Blob connector with the registry."""
    if not AZURE_BLOB_AVAILABLE:
        return

    register_connector(
        subtype=ConnectorSubtype.AZURE_BLOB,
        connector_class=AzureBlobConnector,
        name="Azure Blob Storage",
        description="Connect to Azure Blob Storage for claims files (EDI, CSV)",
        connector_type=ConnectorType.FILE,
        config_schema=AZURE_BLOB_CONFIG_SCHEMA,
        supported_data_types=[
            DataType.CLAIMS,
            DataType.ELIGIBILITY,
            DataType.PROVIDERS,
            DataType.REFERENCE,
        ],
    )


# Auto-register on import
_register_azure_blob()
