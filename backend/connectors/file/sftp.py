"""SFTP connector for file-based data extraction.

Provides connectivity to SFTP servers for extracting healthcare data
files including EDI 837 claims and CSV exports.
"""

from __future__ import annotations

import fnmatch
import logging
import stat
import time
from datetime import datetime
from typing import Any

from ..models import ConnectionTestResult, ConnectorSubtype, ConnectorType, DataType
from ..registry import register_connector
from .base_file import BaseFileConnector, FileConnectionError, FileInfo

logger = logging.getLogger(__name__)

# Try to import paramiko
try:
    import paramiko
    from paramiko import SFTPClient, Transport
    from paramiko.ssh_exception import SSHException

    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    paramiko = None  # type: ignore
    SFTPClient = Any  # type: ignore
    Transport = Any  # type: ignore
    SSHException = Exception  # type: ignore
    logger.warning("paramiko not installed - SFTP connector disabled")


class SFTPConnector(BaseFileConnector):
    """Connector for SFTP servers.

    Supports:
    - Password and key-based authentication
    - Custom port configuration
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
        """Initialize SFTP connector.

        Args:
            connector_id: Unique identifier
            name: Human-readable name
            config: SFTP configuration with keys:
                - host: SFTP server hostname
                - port: SFTP port (default: 22)
                - username: Login username
                - password: Login password (optional if using key)
                - private_key: SSH private key content (optional)
                - private_key_passphrase: Key passphrase (optional)
                - remote_path: Base path on server
                - path_pattern: Glob pattern for files
                - file_format: edi_837, csv, json
            batch_size: Records per batch
        """
        if not PARAMIKO_AVAILABLE:
            raise ImportError(
                "paramiko is required. Install with: pip install paramiko"
            )

        super().__init__(connector_id, name, config, batch_size)
        self._transport: Transport | None = None
        self._sftp: SFTPClient | None = None

    def connect(self) -> None:
        """Establish connection to SFTP server."""
        if self._connected:
            return

        try:
            host = self.config.get("host")
            port = int(self.config.get("port", 22))
            username = self.config.get("username")
            password = self.config.get("password")
            private_key = self.config.get("private_key")
            passphrase = self.config.get("private_key_passphrase")

            if not host or not username:
                raise ValueError("Host and username are required")

            # Create transport
            self._transport = paramiko.Transport((host, port))

            # Authenticate
            if private_key:
                # Key-based authentication
                import io

                key_file = io.StringIO(private_key)
                try:
                    pkey = paramiko.RSAKey.from_private_key(
                        key_file, password=passphrase
                    )
                except SSHException:
                    key_file.seek(0)
                    pkey = paramiko.Ed25519Key.from_private_key(
                        key_file, password=passphrase
                    )

                self._transport.connect(username=username, pkey=pkey)
            else:
                # Password authentication
                if not password:
                    raise ValueError("Password or private key is required")
                self._transport.connect(username=username, password=password)

            # Open SFTP channel
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)

            self._connected = True
            self._log("info", f"Connected to SFTP server: {host}")

        except SSHException as e:
            self._cleanup_connection()
            raise FileConnectionError(
                f"Failed to connect to SFTP: {e}", self.connector_id
            ) from e
        except Exception as e:
            self._cleanup_connection()
            raise FileConnectionError(
                f"SFTP connection error: {e}", self.connector_id
            ) from e

    def _cleanup_connection(self) -> None:
        """Clean up SFTP connection resources."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None

        if self._transport:
            try:
                self._transport.close()
            except Exception:
                pass
            self._transport = None

    def disconnect(self) -> None:
        """Disconnect from SFTP server."""
        self._cleanup_connection()
        super().disconnect()

    def test_connection(self) -> ConnectionTestResult:
        """Test SFTP connection."""
        start_time = time.time()

        try:
            host = self.config.get("host")
            port = int(self.config.get("port", 22))
            username = self.config.get("username")
            password = self.config.get("password")
            private_key = self.config.get("private_key")
            passphrase = self.config.get("private_key_passphrase")

            if not host or not username:
                return ConnectionTestResult(
                    success=False,
                    message="Host and username are required",
                    latency_ms=None,
                    details={},
                )

            # Create transport
            transport = paramiko.Transport((host, port))

            try:
                # Authenticate
                if private_key:
                    import io

                    key_file = io.StringIO(private_key)
                    try:
                        pkey = paramiko.RSAKey.from_private_key(
                            key_file, password=passphrase
                        )
                    except SSHException:
                        key_file.seek(0)
                        pkey = paramiko.Ed25519Key.from_private_key(
                            key_file, password=passphrase
                        )
                    transport.connect(username=username, pkey=pkey)
                else:
                    transport.connect(username=username, password=password)

                sftp = paramiko.SFTPClient.from_transport(transport)

                # List directory
                remote_path = self.config.get("remote_path", "/")
                try:
                    files = sftp.listdir(remote_path)
                    file_count = len(files)
                    sample_files = files[:5]
                except IOError:
                    file_count = 0
                    sample_files = []

                latency_ms = (time.time() - start_time) * 1000

                sftp.close()

                return ConnectionTestResult(
                    success=True,
                    message=f"Successfully connected to SFTP server: {host}",
                    latency_ms=round(latency_ms, 2),
                    details={
                        "host": host,
                        "port": port,
                        "username": username,
                        "remote_path": remote_path,
                        "files_found": file_count,
                        "sample_files": sample_files,
                    },
                )

            finally:
                transport.close()

        except SSHException as e:
            latency_ms = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                success=False,
                message=f"SSH error: {str(e)[:200]}",
                latency_ms=round(latency_ms, 2),
                details={"error_type": "SSHException"},
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Connection failed: {str(e)[:200]}",
                latency_ms=None,
                details={"error_type": type(e).__name__},
            )

    def _list_files(self, pattern: str) -> list[FileInfo]:
        """List files on SFTP server matching the pattern.

        Args:
            pattern: Glob pattern for matching files

        Returns:
            List of FileInfo objects
        """
        if not self._sftp:
            self.connect()

        remote_path = self.config.get("remote_path", "/")
        files = []

        try:
            for entry in self._sftp.listdir_attr(remote_path):
                # Skip directories
                if stat.S_ISDIR(entry.st_mode):
                    continue

                filename = entry.filename

                # Apply pattern matching
                if pattern and not fnmatch.fnmatch(filename, pattern):
                    continue

                # Get modification time
                modified_at = None
                if entry.st_mtime:
                    modified_at = datetime.fromtimestamp(entry.st_mtime)

                full_path = f"{remote_path.rstrip('/')}/{filename}"

                files.append(
                    FileInfo(
                        name=filename,
                        path=full_path,
                        size=entry.st_size or 0,
                        modified_at=modified_at,
                        is_directory=False,
                    )
                )

        except IOError as e:
            logger.error(f"Error listing SFTP directory: {e}")
            raise FileConnectionError(f"Failed to list files: {e}", self.connector_id)

        return files

    def _download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from SFTP.

        Args:
            remote_path: Remote file path
            local_path: Local destination path

        Returns:
            True if successful
        """
        if not self._sftp:
            self.connect()

        try:
            self._sftp.get(remote_path, local_path)
            return True
        except IOError as e:
            logger.error(f"Error downloading {remote_path}: {e}")
            return False

    def _archive_file(self, source_path: str, archive_path: str) -> bool:
        """Move a file to archive location on SFTP.

        Args:
            source_path: Source file path
            archive_path: Destination path

        Returns:
            True if successful
        """
        if not self._sftp:
            self.connect()

        try:
            # Ensure archive directory exists
            archive_dir = "/".join(archive_path.split("/")[:-1])
            try:
                self._sftp.stat(archive_dir)
            except IOError:
                self._sftp.mkdir(archive_dir)

            # Rename (move) file
            self._sftp.rename(source_path, archive_path)
            return True
        except IOError as e:
            logger.error(f"Error archiving {source_path}: {e}")
            return False


# Configuration schema for the UI
SFTP_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["host", "username"],
    "properties": {
        "host": {
            "type": "string",
            "title": "Host",
            "description": "SFTP server hostname or IP",
        },
        "port": {
            "type": "integer",
            "title": "Port",
            "description": "SFTP port",
            "default": 22,
            "minimum": 1,
            "maximum": 65535,
        },
        "username": {
            "type": "string",
            "title": "Username",
            "description": "Login username",
        },
        "password": {
            "type": "string",
            "title": "Password",
            "description": "Login password (or use private key)",
            "format": "password",
        },
        "private_key": {
            "type": "string",
            "title": "Private Key",
            "description": "SSH private key content (PEM format)",
            "format": "textarea",
        },
        "private_key_passphrase": {
            "type": "string",
            "title": "Key Passphrase",
            "description": "Private key passphrase (if encrypted)",
            "format": "password",
        },
        "remote_path": {
            "type": "string",
            "title": "Remote Path",
            "description": "Base directory on SFTP server",
            "default": "/",
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
            "description": "Destination directory for archived files",
        },
    },
}


def _register_sftp() -> None:
    """Register SFTP connector with the registry."""
    if not PARAMIKO_AVAILABLE:
        return

    register_connector(
        subtype=ConnectorSubtype.SFTP,
        connector_class=SFTPConnector,
        name="SFTP",
        description="Connect to SFTP servers for claims files (EDI, CSV)",
        connector_type=ConnectorType.FILE,
        config_schema=SFTP_CONFIG_SCHEMA,
        supported_data_types=[
            DataType.CLAIMS,
            DataType.ELIGIBILITY,
            DataType.PROVIDERS,
            DataType.REFERENCE,
        ],
    )


# Auto-register on import
_register_sftp()
