"""MySQL connector using SQLAlchemy and PyMySQL/mysql-connector.

Provides connection, schema discovery, and data extraction for MySQL databases.
"""

from __future__ import annotations

import urllib.parse

from ..models import ConnectorSubtype, ConnectorType, DataType
from ..registry import register_connector
from .base_db import BaseDatabaseConnector


class MySQLConnector(BaseDatabaseConnector):
    """Connector for MySQL/MariaDB databases.

    Supports:
    - SSL connections
    - Custom SQL queries
    - Incremental sync with watermark columns
    - Batch extraction with server-side cursors
    """

    def _get_driver_name(self) -> str:
        """Get the MySQL driver name."""
        return "mysql"

    def _build_connection_string(self) -> str:
        """Build MySQL connection string.

        Format: mysql+pymysql://user:password@host:port/database?charset=utf8mb4

        Returns:
            SQLAlchemy connection URL
        """
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 3306)
        database = self.config.get("database", "")
        username = self.config.get("username", "root")
        password = self.config.get("password", "")
        charset = self.config.get("charset", "utf8mb4")

        # URL-encode password to handle special characters
        encoded_password = urllib.parse.quote_plus(password) if password else ""

        # Build connection string using PyMySQL driver
        connection_string = (
            f"mysql+pymysql://{username}:{encoded_password}@{host}:{port}/{database}"
        )

        # Add charset
        params = [f"charset={charset}"]

        # Add SSL if required
        ssl_mode = self.config.get("ssl_mode")
        if ssl_mode and ssl_mode != "disabled":
            # PyMySQL uses ssl_disabled=False for enabling SSL
            params.append("ssl=true")

        if params:
            connection_string += "?" + "&".join(params)

        return connection_string


# Configuration schema for the UI
MYSQL_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["host", "port", "database", "username"],
    "properties": {
        "host": {
            "type": "string",
            "title": "Host",
            "description": "MySQL server hostname or IP",
            "default": "localhost",
        },
        "port": {
            "type": "integer",
            "title": "Port",
            "description": "MySQL server port",
            "default": 3306,
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
                "disabled",
                "preferred",
                "required",
                "verify_ca",
                "verify_identity",
            ],
            "default": "preferred",
        },
        "charset": {
            "type": "string",
            "title": "Character Set",
            "description": "Database character set",
            "default": "utf8mb4",
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
def _register_mysql() -> None:
    """Register MySQL connector with the registry."""
    register_connector(
        subtype=ConnectorSubtype.MYSQL,
        connector_class=MySQLConnector,
        name="MySQL",
        description="Connect to MySQL/MariaDB databases for claims and provider data",
        connector_type=ConnectorType.DATABASE,
        config_schema=MYSQL_CONFIG_SCHEMA,
        supported_data_types=[
            DataType.CLAIMS,
            DataType.ELIGIBILITY,
            DataType.PROVIDERS,
            DataType.REFERENCE,
        ],
    )


# Auto-register on import
_register_mysql()
