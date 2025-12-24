"""SQL Server connector using SQLAlchemy and pymssql.

Provides connection, schema discovery, and data extraction for Microsoft SQL Server databases.
"""

from __future__ import annotations

import urllib.parse

from ..models import ConnectorSubtype, ConnectorType, DataType
from ..registry import register_connector
from .base_db import BaseDatabaseConnector


class SQLServerConnector(BaseDatabaseConnector):
    """Connector for Microsoft SQL Server databases.

    Supports:
    - Windows Authentication and SQL Server Authentication
    - SSL/TLS encrypted connections
    - Schema-qualified table access
    - Custom SQL queries
    - Incremental sync with watermark columns
    - Batch extraction with server-side cursors
    """

    def _get_driver_name(self) -> str:
        """Get the SQL Server driver name."""
        return "mssql"

    def _build_connection_string(self) -> str:
        """Build SQL Server connection string.

        Format: mssql+pymssql://user:password@host:port/database

        Returns:
            SQLAlchemy connection URL
        """
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 1433)
        database = self.config.get("database", "master")
        username = self.config.get("username", "sa")
        password = self.config.get("password", "")

        # URL-encode password to handle special characters
        encoded_password = urllib.parse.quote_plus(password) if password else ""

        # Build base connection string using pymssql driver
        connection_string = (
            f"mssql+pymssql://{username}:{encoded_password}@{host}:{port}/{database}"
        )

        # Build query parameters
        params = []

        # Add charset if specified
        charset = self.config.get("charset", "UTF-8")
        if charset:
            params.append(f"charset={charset}")

        # Add TDS version for compatibility
        tds_version = self.config.get("tds_version")
        if tds_version:
            params.append(f"tds_version={tds_version}")

        if params:
            connection_string += "?" + "&".join(params)

        return connection_string


# Configuration schema for the UI
SQLSERVER_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["host", "port", "database", "username"],
    "properties": {
        "host": {
            "type": "string",
            "title": "Host",
            "description": "SQL Server hostname or IP address",
            "default": "localhost",
        },
        "port": {
            "type": "integer",
            "title": "Port",
            "description": "SQL Server port",
            "default": 1433,
            "minimum": 1,
            "maximum": 65535,
        },
        "database": {
            "type": "string",
            "title": "Database",
            "description": "Database name to connect to",
        },
        "username": {
            "type": "string",
            "title": "Username",
            "description": "SQL Server login username",
        },
        "password": {
            "type": "string",
            "title": "Password",
            "description": "SQL Server login password",
            "format": "password",
        },
        "schema_name": {
            "type": "string",
            "title": "Schema",
            "description": "Database schema (default: dbo)",
            "default": "dbo",
        },
        "encrypt": {
            "type": "string",
            "title": "Encryption",
            "description": "Connection encryption mode",
            "enum": ["yes", "no", "strict"],
            "default": "yes",
        },
        "trust_server_certificate": {
            "type": "boolean",
            "title": "Trust Server Certificate",
            "description": "Trust self-signed certificates (development only)",
            "default": False,
        },
        "tds_version": {
            "type": "string",
            "title": "TDS Version",
            "description": "Tabular Data Stream protocol version",
            "enum": ["7.0", "7.1", "7.2", "7.3", "7.4"],
            "default": "7.4",
        },
        "charset": {
            "type": "string",
            "title": "Character Set",
            "description": "Character encoding for the connection",
            "default": "UTF-8",
        },
        "table": {
            "type": "string",
            "title": "Table",
            "description": "Table to extract data from",
        },
        "query": {
            "type": "string",
            "title": "Custom Query",
            "description": "Custom SQL query (overrides table)",
            "format": "sql",
        },
        "watermark_column": {
            "type": "string",
            "title": "Watermark Column",
            "description": "Column for incremental sync (e.g., ModifiedDate)",
        },
    },
}


# Register the connector
def _register_sqlserver() -> None:
    """Register SQL Server connector with the registry."""
    register_connector(
        subtype=ConnectorSubtype.SQLSERVER,
        connector_class=SQLServerConnector,
        name="SQL Server",
        description="Connect to Microsoft SQL Server databases for claims, eligibility, and provider data",
        connector_type=ConnectorType.DATABASE,
        config_schema=SQLSERVER_CONFIG_SCHEMA,
        supported_data_types=[
            DataType.CLAIMS,
            DataType.ELIGIBILITY,
            DataType.PROVIDERS,
            DataType.REFERENCE,
        ],
    )


# Auto-register on import
_register_sqlserver()
