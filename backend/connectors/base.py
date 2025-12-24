"""Base connector abstract class.

Defines the interface that all data source connectors must implement.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from .models import (
        ConnectionTestResult,
        SchemaDiscoveryResult,
        SyncMode,
    )

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Abstract base class for all data source connectors.

    Connectors handle:
    - Connection management (connect, disconnect, test)
    - Schema discovery (list tables, columns)
    - Data extraction (batch reads with optional watermarking)

    Subclasses must implement the abstract methods for their specific
    data source type (database, API, file system).
    """

    def __init__(
        self,
        connector_id: str,
        name: str,
        config: dict[str, Any],
        batch_size: int = 1000,
    ) -> None:
        """Initialize the connector.

        Args:
            connector_id: Unique identifier for this connector
            name: Human-readable name
            config: Connection configuration (type-specific)
            batch_size: Number of records per batch during extraction
        """
        self.connector_id = connector_id
        self.name = name
        self.config = config
        self.batch_size = batch_size
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if the connector is currently connected."""
        return self._connected

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the data source.

        Raises:
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the data source."""
        pass

    @abstractmethod
    def test_connection(self) -> "ConnectionTestResult":
        """Test the connection without keeping it open.

        Returns:
            ConnectionTestResult with success status and details
        """
        pass

    @abstractmethod
    def discover_schema(self) -> "SchemaDiscoveryResult":
        """Discover the schema of the data source.

        Returns:
            SchemaDiscoveryResult with tables, columns, and sample data
        """
        pass

    @abstractmethod
    def extract(
        self,
        sync_mode: "SyncMode",
        watermark_value: str | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        """Extract data from the source in batches.

        Args:
            sync_mode: FULL or INCREMENTAL extraction
            watermark_value: Last sync watermark for incremental mode

        Yields:
            Batches of records as dictionaries
        """
        pass

    @abstractmethod
    def get_current_watermark(self) -> str | None:
        """Get the current watermark value for incremental sync.

        Returns:
            Current watermark value (e.g., max timestamp), or None
        """
        pass

    def __enter__(self) -> "BaseConnector":
        """Context manager entry - connect."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - disconnect."""
        self.disconnect()

    def _log(self, level: str, message: str, **context: Any) -> None:
        """Log a message with connector context.

        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            **context: Additional context to include
        """
        log_fn = getattr(logger, level.lower(), logger.info)
        log_fn(
            f"[{self.name}] {message}",
            extra={"connector_id": self.connector_id, **context},
        )


class ConnectorError(Exception):
    """Base exception for connector errors."""

    def __init__(self, message: str, connector_id: str | None = None) -> None:
        super().__init__(message)
        self.connector_id = connector_id


class ConnectionError(ConnectorError):
    """Error connecting to a data source."""

    pass


class ExtractionError(ConnectorError):
    """Error extracting data from a source."""

    pass


class SchemaDiscoveryError(ConnectorError):
    """Error discovering schema from a source."""

    pass
