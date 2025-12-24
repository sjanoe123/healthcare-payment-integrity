"""File-based connectors for S3, SFTP, Azure Blob, and local file systems.

Provides data extraction from file-based sources with support for
various file formats including EDI 837, CSV, and JSON.
"""

from .base_file import BaseFileConnector, FileConnectionError
from .s3 import S3Connector
from .sftp import SFTPConnector
from .azure_blob import AzureBlobConnector

__all__ = [
    "BaseFileConnector",
    "FileConnectionError",
    "S3Connector",
    "SFTPConnector",
    "AzureBlobConnector",
]
