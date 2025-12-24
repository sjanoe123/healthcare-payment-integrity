"""Data Source Connector Framework.

Provides a unified interface for connecting to various data sources:
- Databases (PostgreSQL, MySQL, SQL Server)
- APIs (REST, FHIR)
- File systems (S3, SFTP, Azure Blob)

Example usage:
    from connectors import create_connector, ConnectorSubtype

    connector = create_connector(
        subtype=ConnectorSubtype.POSTGRESQL,
        connector_id="my-pg-source",
        name="Production Database",
        config={
            "host": "db.example.com",
            "port": 5432,
            "database": "claims",
            "username": "reader",
            "password": "secret",
        },
    )

    # Test connection
    result = connector.test_connection()
    if result.success:
        # Extract data
        with connector:
            for batch in connector.extract(sync_mode=SyncMode.FULL):
                process_batch(batch)
"""

from .base import (
    BaseConnector,
    ConnectionError,
    ConnectorError,
    ExtractionError,
    SchemaDiscoveryError,
)
from .models import (
    APIConnectionConfig,
    ConnectionTestResult,
    ConnectorCreate,
    ConnectorListResponse,
    ConnectorResponse,
    ConnectorStatus,
    ConnectorSubtype,
    ConnectorType,
    ConnectorTypeInfo,
    ConnectorUpdate,
    DatabaseConnectionConfig,
    DataType,
    FileConnectionConfig,
    SchemaDiscoveryResult,
    SyncJobCreate,
    SyncJobListResponse,
    SyncJobLogEntry,
    SyncJobLogsResponse,
    SyncJobResponse,
    SyncJobStatus,
    SyncJobType,
    SyncMode,
)
from .registry import (
    ConnectorRegistry,
    create_connector,
    get_connector_info,
    get_registry,
    list_connector_types,
    register_connector,
)
from .config_loader import (
    ConfigLoader,
    ConfigValidationError,
    load_connectors_from_config,
)

__all__ = [
    # Base classes
    "BaseConnector",
    # Exceptions
    "ConnectorError",
    "ConnectionError",
    "ExtractionError",
    "SchemaDiscoveryError",
    # Enums
    "ConnectorType",
    "ConnectorSubtype",
    "ConnectorStatus",
    "DataType",
    "SyncMode",
    "SyncJobStatus",
    "SyncJobType",
    # Config models
    "DatabaseConnectionConfig",
    "APIConnectionConfig",
    "FileConnectionConfig",
    # Request/Response models
    "ConnectorCreate",
    "ConnectorUpdate",
    "ConnectorResponse",
    "ConnectorListResponse",
    "ConnectionTestResult",
    "SchemaDiscoveryResult",
    "ConnectorTypeInfo",
    "SyncJobCreate",
    "SyncJobResponse",
    "SyncJobListResponse",
    "SyncJobLogEntry",
    "SyncJobLogsResponse",
    # Registry
    "ConnectorRegistry",
    "get_registry",
    "register_connector",
    "create_connector",
    "get_connector_info",
    "list_connector_types",
    # Config Loader
    "ConfigLoader",
    "ConfigValidationError",
    "load_connectors_from_config",
]
