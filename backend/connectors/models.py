"""Pydantic models for data source connectors.

Defines the data structures for connector configurations, sync jobs,
and related entities used throughout the connector framework.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Regex pattern for validating cron expressions (5 or 6 parts)
CRON_PATTERN = re.compile(
    r"^(\*|([0-5]?\d))(/\d+)?\s+"  # minute or second
    r"(\*|([01]?\d|2[0-3]))(/\d+)?\s+"  # hour
    r"(\*|([12]?\d|3[01]))(/\d+)?\s+"  # day of month
    r"(\*|(1[0-2]|0?[1-9]))(/\d+)?\s+"  # month
    r"(\*|[0-6])(/\d+)?$",  # day of week
    re.IGNORECASE,
)

# Pattern for SQL identifiers (table/column names)
SQL_IDENTIFIER_PATTERN = re.compile(
    r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$"
)


class ConnectorType(str, Enum):
    """Types of data source connectors."""

    DATABASE = "database"
    API = "api"
    FILE = "file"


class ConnectorSubtype(str, Enum):
    """Specific connector implementations."""

    # Database subtypes
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"

    # API subtypes
    REST = "rest"
    FHIR = "fhir"

    # File subtypes
    S3 = "s3"
    SFTP = "sftp"
    AZURE_BLOB = "azure_blob"
    LOCAL = "local"


class DataType(str, Enum):
    """Types of healthcare data handled by connectors."""

    CLAIMS = "claims"
    ELIGIBILITY = "eligibility"
    PROVIDERS = "providers"
    REFERENCE = "reference"


class ConnectorStatus(str, Enum):
    """Connector operational status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    TESTING = "testing"


class SyncMode(str, Enum):
    """Data synchronization modes."""

    FULL = "full"
    INCREMENTAL = "incremental"


class SyncJobStatus(str, Enum):
    """Status of a sync job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncJobType(str, Enum):
    """How the sync job was triggered."""

    SCHEDULED = "scheduled"
    MANUAL = "manual"


# --- Request/Response Models ---


class DatabaseConnectionConfig(BaseModel):
    """Configuration for database connectors."""

    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., ge=1, le=65535)
    database: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(exclude=True)  # Stored encrypted separately
    ssl_mode: str = "prefer"
    schema_name: str | None = None
    query: str | None = None  # Custom SQL query for extraction
    table: str | None = None  # Table name if not using query
    watermark_column: str | None = None  # For incremental sync

    @field_validator("schema_name", "table", "watermark_column")
    @classmethod
    def validate_sql_identifier(cls, v: str | None) -> str | None:
        """Validate SQL identifiers to prevent injection."""
        if v is None:
            return v
        if not SQL_IDENTIFIER_PATTERN.match(v):
            raise ValueError(
                f"Invalid SQL identifier: '{v}'. "
                "Only alphanumeric characters and underscores allowed."
            )
        return v

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str | None) -> str | None:
        """Validate custom query doesn't contain dangerous patterns."""
        if v is None:
            return v
        # Check for multiple statements or comment injection
        if ";" in v or "--" in v:
            raise ValueError("Custom queries cannot contain ';' or '--' characters")
        return v


class APIConnectionConfig(BaseModel):
    """Configuration for API connectors."""

    base_url: str
    auth_type: str = "none"  # none, api_key, oauth2, basic, bearer
    api_key: str | None = Field(default=None, exclude=True)
    bearer_token: str | None = Field(default=None, exclude=True)
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = Field(default=None, exclude=True)
    oauth_token_url: str | None = None
    oauth_scopes: list[str] = []
    headers: dict[str, str] = {}
    endpoint: str = "/"
    pagination_type: str = "none"  # none, offset, cursor, link
    rate_limit: int = 100  # requests per minute


class FileConnectionConfig(BaseModel):
    """Configuration for file connectors."""

    # S3
    bucket: str | None = None
    aws_region: str | None = None
    aws_access_key: str | None = Field(default=None, exclude=True)
    aws_secret_key: str | None = Field(default=None, exclude=True)

    # Azure Blob Storage
    azure_container: str | None = None
    azure_account_name: str | None = None
    account_key: str | None = Field(default=None, exclude=True)
    sas_token: str | None = Field(default=None, exclude=True)
    azure_connection_string: str | None = Field(default=None, exclude=True)

    # SFTP
    host: str | None = None
    port: int = 22
    username: str | None = None
    password: str | None = Field(default=None, exclude=True)
    private_key: str | None = Field(default=None, exclude=True)

    # Common
    path_pattern: str = "*"  # Glob pattern for file matching
    file_format: str = "csv"  # csv, json, edi_837
    archive_after_sync: bool = False


class ConnectorConfigUnion(BaseModel):
    """Union type for connection configurations."""

    database: DatabaseConnectionConfig | None = None
    api: APIConnectionConfig | None = None
    file: FileConnectionConfig | None = None


class ConnectorCreate(BaseModel):
    """Request model for creating a connector."""

    name: str = Field(..., min_length=1, max_length=100)
    connector_type: ConnectorType
    subtype: ConnectorSubtype
    data_type: DataType
    connection_config: dict[str, Any]
    sync_schedule: str | None = None  # Cron expression
    sync_mode: SyncMode = SyncMode.INCREMENTAL
    batch_size: int = Field(default=1000, ge=100, le=10000)
    field_mapping_id: str | None = None
    created_by: str | None = None

    @field_validator("sync_schedule")
    @classmethod
    def validate_cron_schedule(cls, v: str | None) -> str | None:
        """Validate cron expression format."""
        if v is None:
            return v
        # Remove extra whitespace
        v = " ".join(v.split())
        # Basic validation: should have 5 space-separated parts
        parts = v.split()
        if len(parts) not in (5, 6):
            raise ValueError(
                "Invalid cron expression. Expected 5 or 6 space-separated fields: "
                "minute hour day month day_of_week [second]"
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate connector name doesn't contain dangerous characters."""
        # Remove leading/trailing whitespace
        v = v.strip()
        # Check for script injection patterns
        if "<" in v or ">" in v or "&" in v:
            raise ValueError("Connector name cannot contain HTML special characters")
        return v


class ConnectorUpdate(BaseModel):
    """Request model for updating a connector."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    connection_config: dict[str, Any] | None = None
    sync_schedule: str | None = None
    sync_mode: SyncMode | None = None
    batch_size: int | None = Field(default=None, ge=100, le=10000)
    field_mapping_id: str | None = None


class ConnectorResponse(BaseModel):
    """Response model for connector details."""

    id: str
    name: str
    connector_type: ConnectorType
    subtype: ConnectorSubtype
    data_type: DataType
    connection_config: dict[str, Any]  # Secrets redacted
    sync_schedule: str | None
    sync_mode: SyncMode
    batch_size: int
    field_mapping_id: str | None
    status: ConnectorStatus
    last_sync_at: datetime | None
    last_sync_status: SyncJobStatus | None
    created_at: datetime
    created_by: str | None


class ConnectorListResponse(BaseModel):
    """Response model for listing connectors."""

    connectors: list[ConnectorResponse]
    total: int


class ConnectionTestResult(BaseModel):
    """Result of testing a connector connection."""

    success: bool
    message: str
    latency_ms: float | None = None
    details: dict[str, Any] = {}


class SchemaDiscoveryResult(BaseModel):
    """Result of discovering schema from a data source."""

    tables: list[str] = []
    columns: dict[str, list[dict[str, str]]] = {}  # table -> [{name, type}]
    sample_data: dict[str, list[dict[str, Any]]] = {}  # table -> rows


# --- Sync Job Models ---


class SyncJobCreate(BaseModel):
    """Request model for triggering a manual sync."""

    sync_mode: SyncMode | None = None  # Override connector default
    triggered_by: str | None = None


class SyncJobResponse(BaseModel):
    """Response model for sync job details."""

    id: str
    connector_id: str
    connector_name: str | None = None
    job_type: SyncJobType
    sync_mode: SyncMode
    status: SyncJobStatus
    started_at: datetime | None
    completed_at: datetime | None
    total_records: int
    processed_records: int
    failed_records: int
    watermark_value: str | None
    error_message: str | None
    triggered_by: str | None


class SyncJobListResponse(BaseModel):
    """Response model for listing sync jobs."""

    jobs: list[SyncJobResponse]
    total: int


class SyncJobLogEntry(BaseModel):
    """A single log entry for a sync job."""

    id: str
    timestamp: datetime
    level: str  # DEBUG, INFO, WARNING, ERROR
    message: str
    context: dict[str, Any] | None = None


class SyncJobLogsResponse(BaseModel):
    """Response model for sync job logs."""

    job_id: str
    logs: list[SyncJobLogEntry]


# --- Connector Type Info ---


class ConnectorTypeInfo(BaseModel):
    """Information about an available connector type."""

    type: ConnectorType
    subtype: ConnectorSubtype
    name: str
    description: str
    config_schema: dict[str, Any]  # JSON Schema for connection_config
    supported_data_types: list[DataType]
