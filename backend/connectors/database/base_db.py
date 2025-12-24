"""Base database connector using SQLAlchemy.

Provides common functionality for all database connectors including
connection management, schema discovery, and batch data extraction.
"""

from __future__ import annotations

import logging
import time
from abc import abstractmethod
from typing import Any, Iterator

from ..base import BaseConnector, ConnectorError
from ..models import ConnectionTestResult, SchemaDiscoveryResult, SyncMode

logger = logging.getLogger(__name__)

# Try to import SQLAlchemy
try:
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import SQLAlchemyError

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Engine = Any  # type: ignore
    SQLAlchemyError = Exception  # type: ignore


class DatabaseConnectionError(ConnectorError):
    """Error connecting to a database."""

    pass


class BaseDatabaseConnector(BaseConnector):
    """Base class for database connectors using SQLAlchemy.

    Provides common functionality for:
    - Connection string building
    - Schema discovery (tables, columns)
    - Batch data extraction with watermarking
    - Connection testing

    Subclasses must implement:
    - _build_connection_string(): Build the SQLAlchemy connection URL
    - _get_driver_name(): Return the driver name for the database
    """

    def __init__(
        self,
        connector_id: str,
        name: str,
        config: dict[str, Any],
        batch_size: int = 1000,
    ) -> None:
        """Initialize the database connector.

        Args:
            connector_id: Unique identifier
            name: Human-readable name
            config: Database connection configuration with keys:
                - host: Database host
                - port: Database port
                - database: Database name
                - username: Database username
                - password: Database password
                - ssl_mode: SSL mode (optional)
                - schema_name: Schema to use (optional)
                - table: Table name for extraction (optional)
                - query: Custom SQL query (optional)
                - watermark_column: Column for incremental sync (optional)
            batch_size: Records per batch
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "SQLAlchemy is required for database connectors. "
                "Install with: pip install sqlalchemy"
            )

        super().__init__(connector_id, name, config, batch_size)
        self._engine: Engine | None = None
        self._connection: Any = None

    @abstractmethod
    def _build_connection_string(self) -> str:
        """Build the SQLAlchemy connection URL.

        Returns:
            SQLAlchemy connection string
        """
        pass

    @abstractmethod
    def _get_driver_name(self) -> str:
        """Get the database driver name.

        Returns:
            Driver name (e.g., 'postgresql', 'mysql')
        """
        pass

    def connect(self) -> None:
        """Establish database connection."""
        if self._connected:
            return

        try:
            connection_string = self._build_connection_string()
            self._engine = create_engine(
                connection_string,
                pool_pre_ping=True,  # Check connection health
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
            )
            # Test the connection
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._connected = True
            self._log("info", "Connected successfully")
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(
                f"Failed to connect: {e}", self.connector_id
            ) from e

    def disconnect(self) -> None:
        """Close database connection."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        self._connected = False
        self._log("info", "Disconnected")

    def test_connection(self) -> ConnectionTestResult:
        """Test the database connection."""
        start_time = time.time()

        try:
            connection_string = self._build_connection_string()
            engine = create_engine(connection_string, pool_pre_ping=True)

            with engine.connect() as conn:
                # Execute a simple query
                result = conn.execute(text("SELECT 1"))
                result.fetchone()

            latency_ms = (time.time() - start_time) * 1000

            # Get additional info
            inspector = inspect(engine)
            tables = inspector.get_table_names(schema=self.config.get("schema_name"))

            engine.dispose()

            return ConnectionTestResult(
                success=True,
                message=f"Successfully connected to {self.config.get('database')}",
                latency_ms=round(latency_ms, 2),
                details={
                    "driver": self._get_driver_name(),
                    "database": self.config.get("database"),
                    "host": self.config.get("host"),
                    "tables_found": len(tables),
                    "sample_tables": tables[:5] if tables else [],
                },
            )

        except SQLAlchemyError as e:
            latency_ms = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                success=False,
                message=f"Connection failed: {str(e)[:200]}",
                latency_ms=round(latency_ms, 2),
                details={
                    "error_type": type(e).__name__,
                    "driver": self._get_driver_name(),
                },
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Unexpected error: {str(e)[:200]}",
                latency_ms=None,
                details={"error_type": type(e).__name__},
            )

    def discover_schema(self) -> SchemaDiscoveryResult:
        """Discover database schema (tables and columns)."""
        if not self._engine:
            self.connect()

        assert self._engine is not None

        try:
            inspector = inspect(self._engine)
            schema_name = self.config.get("schema_name")

            # Get all tables
            tables = inspector.get_table_names(schema=schema_name)

            # Get columns for each table
            columns: dict[str, list[dict[str, str]]] = {}
            sample_data: dict[str, list[dict[str, Any]]] = {}

            for table in tables[:20]:  # Limit to first 20 tables
                try:
                    table_columns = inspector.get_columns(table, schema=schema_name)
                    columns[table] = [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col.get("nullable", True),
                        }
                        for col in table_columns
                    ]

                    # Get sample data (first 3 rows)
                    qualified_name = f"{schema_name}.{table}" if schema_name else table
                    with self._engine.connect() as conn:
                        result = conn.execute(
                            text(f"SELECT * FROM {qualified_name} LIMIT 3")
                        )
                        rows = result.fetchall()
                        if rows:
                            col_names = result.keys()
                            sample_data[table] = [
                                dict(zip(col_names, row)) for row in rows
                            ]
                except SQLAlchemyError as e:
                    logger.warning(f"Could not inspect table {table}: {e}")
                    continue

            return SchemaDiscoveryResult(
                tables=tables,
                columns=columns,
                sample_data=sample_data,
            )

        except SQLAlchemyError as e:
            raise DatabaseConnectionError(
                f"Schema discovery failed: {e}", self.connector_id
            ) from e

    def extract(
        self,
        sync_mode: SyncMode,
        watermark_value: str | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        """Extract data from the database in batches.

        Args:
            sync_mode: FULL or INCREMENTAL
            watermark_value: Last watermark for incremental sync

        Yields:
            Batches of records as dictionaries
        """
        if not self._engine:
            self.connect()

        assert self._engine is not None

        # Build query
        query = self._build_extraction_query(sync_mode, watermark_value)

        try:
            with self._engine.connect() as conn:
                # Use server-side cursor for large datasets
                result = conn.execution_options(stream_results=True).execute(
                    text(query)
                )

                batch: list[dict[str, Any]] = []
                column_names = list(result.keys())

                for row in result:
                    record = dict(zip(column_names, row))
                    batch.append(record)

                    if len(batch) >= self.batch_size:
                        yield batch
                        batch = []

                # Yield remaining records
                if batch:
                    yield batch

        except SQLAlchemyError as e:
            raise DatabaseConnectionError(
                f"Data extraction failed: {e}", self.connector_id
            ) from e

    def _build_extraction_query(
        self,
        sync_mode: SyncMode,
        watermark_value: str | None = None,
    ) -> str:
        """Build the SQL query for data extraction.

        Args:
            sync_mode: FULL or INCREMENTAL
            watermark_value: Last watermark for incremental

        Returns:
            SQL query string
        """
        # Use custom query if provided
        custom_query = self.config.get("query")
        if custom_query:
            if sync_mode == SyncMode.INCREMENTAL and watermark_value:
                # Append WHERE clause if query doesn't have one
                watermark_col = self.config.get("watermark_column", "updated_at")
                if "WHERE" not in custom_query.upper():
                    custom_query += f" WHERE {watermark_col} > '{watermark_value}'"
                else:
                    custom_query += f" AND {watermark_col} > '{watermark_value}'"
            return custom_query

        # Build query from table name
        table = self.config.get("table")
        if not table:
            raise ValueError("Either 'query' or 'table' must be specified in config")

        schema_name = self.config.get("schema_name")
        qualified_name = f"{schema_name}.{table}" if schema_name else table

        query = f"SELECT * FROM {qualified_name}"

        # Add watermark filter for incremental sync
        if sync_mode == SyncMode.INCREMENTAL and watermark_value:
            watermark_col = self.config.get("watermark_column", "updated_at")
            query += f" WHERE {watermark_col} > '{watermark_value}'"

        # Add ordering by watermark column if available
        watermark_col = self.config.get("watermark_column")
        if watermark_col:
            query += f" ORDER BY {watermark_col}"

        return query

    def get_current_watermark(self) -> str | None:
        """Get the current maximum watermark value."""
        watermark_col = self.config.get("watermark_column")
        if not watermark_col:
            return None

        if not self._engine:
            self.connect()

        assert self._engine is not None

        table = self.config.get("table")
        if not table:
            return None

        schema_name = self.config.get("schema_name")
        qualified_name = f"{schema_name}.{table}" if schema_name else table

        try:
            with self._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT MAX({watermark_col}) FROM {qualified_name}")
                )
                row = result.fetchone()
                if row and row[0]:
                    return str(row[0])
                return None
        except SQLAlchemyError as e:
            logger.warning(f"Failed to get watermark: {e}")
            return None

    def execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute a custom SQL query and return results.

        Args:
            query: SQL query to execute

        Returns:
            List of result dictionaries
        """
        if not self._engine:
            self.connect()

        assert self._engine is not None

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(query))
                column_names = list(result.keys())
                return [dict(zip(column_names, row)) for row in result.fetchall()]
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(
                f"Query execution failed: {e}", self.connector_id
            ) from e

    def get_row_count(self, table: str | None = None) -> int:
        """Get the row count for a table.

        Args:
            table: Table name (uses config table if not provided)

        Returns:
            Number of rows
        """
        if not self._engine:
            self.connect()

        assert self._engine is not None

        target_table = table or self.config.get("table")
        if not target_table:
            raise ValueError("No table specified")

        schema_name = self.config.get("schema_name")
        qualified_name = (
            f"{schema_name}.{target_table}" if schema_name else target_table
        )

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {qualified_name}"))
                row = result.fetchone()
                return row[0] if row else 0
        except SQLAlchemyError as e:
            raise DatabaseConnectionError(
                f"Row count failed: {e}", self.connector_id
            ) from e
