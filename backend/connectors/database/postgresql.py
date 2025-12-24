"""PostgreSQL connector using SQLAlchemy and psycopg2/asyncpg.

Provides connection, schema discovery, and data extraction for PostgreSQL databases.
"""

from __future__ import annotations

import urllib.parse

from ..models import ConnectorSubtype, ConnectorType, DataType
from ..registry import register_connector
from .base_db import BaseDatabaseConnector


class PostgreSQLConnector(BaseDatabaseConnector):
    """Connector for PostgreSQL databases.

    Supports:
    - SSL connections (require, prefer, disable)
    - Schema-qualified table access
    - Custom SQL queries
    - Incremental sync with watermark columns
    - Batch extraction with server-side cursors
    """

    def _get_driver_name(self) -> str:
        """Get the PostgreSQL driver name."""
        return "postgresql"

    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string.

        Format: postgresql://user:password@host:port/database?sslmode=prefer

        Returns:
            SQLAlchemy connection URL
        """
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 5432)
        database = self.config.get("database", "postgres")
        username = self.config.get("username", "postgres")
        password = self.config.get("password", "")
        ssl_mode = self.config.get("ssl_mode", "prefer")

        # URL-encode password to handle special characters
        encoded_password = urllib.parse.quote_plus(password) if password else ""

        # Build connection string
        connection_string = (
            f"postgresql://{username}:{encoded_password}@{host}:{port}/{database}"
        )

        # Add SSL mode
        if ssl_mode:
            connection_string += f"?sslmode={ssl_mode}"

        return connection_string


# Configuration schema for the UI
POSTGRESQL_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["host", "port", "database", "username"],
    "properties": {
        "host": {
            "type": "string",
            "title": "Host",
            "description": "PostgreSQL server hostname or IP",
            "default": "localhost",
        },
        "port": {
            "type": "integer",
            "title": "Port",
            "description": "PostgreSQL server port",
            "default": 5432,
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
            "description": "Database username",
        },
        "password": {
            "type": "string",
            "title": "Password",
            "description": "Database password",
            "format": "password",
        },
        "ssl_mode": {
            "type": "string",
            "title": "SSL Mode",
            "description": "SSL connection mode",
            "enum": [
                "disable",
                "allow",
                "prefer",
                "require",
                "verify-ca",
                "verify-full",
            ],
            "default": "prefer",
        },
        "schema_name": {
            "type": "string",
            "title": "Schema",
            "description": "Database schema (default: public)",
            "default": "public",
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
            "description": "Column for incremental sync (e.g., updated_at)",
        },
    },
}


# Register the connector
def _register_postgresql() -> None:
    """Register PostgreSQL connector with the registry."""
    register_connector(
        subtype=ConnectorSubtype.POSTGRESQL,
        connector_class=PostgreSQLConnector,
        name="PostgreSQL",
        description="Connect to PostgreSQL databases for claims, eligibility, and provider data",
        connector_type=ConnectorType.DATABASE,
        config_schema=POSTGRESQL_CONFIG_SCHEMA,
        supported_data_types=[
            DataType.CLAIMS,
            DataType.ELIGIBILITY,
            DataType.PROVIDERS,
            DataType.REFERENCE,
        ],
    )


# Auto-register on import
_register_postgresql()
