"""Connector registry for managing available connector types.

The registry pattern allows dynamic registration of connector implementations
and provides factory methods for instantiating connectors by type.
"""

from __future__ import annotations

import logging
from typing import Any, Type

from .base import BaseConnector
from .models import (
    ConnectorSubtype,
    ConnectorType,
    ConnectorTypeInfo,
    DataType,
)

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """Registry for connector implementations.

    Maintains a mapping of connector subtypes to their implementation classes
    and provides factory methods for creating connector instances.
    """

    def __init__(self) -> None:
        self._connectors: dict[ConnectorSubtype, Type[BaseConnector]] = {}
        self._type_info: dict[ConnectorSubtype, ConnectorTypeInfo] = {}

    def register(
        self,
        subtype: ConnectorSubtype,
        connector_class: Type[BaseConnector],
        type_info: ConnectorTypeInfo,
    ) -> None:
        """Register a connector implementation.

        Args:
            subtype: The connector subtype (e.g., POSTGRESQL, S3)
            connector_class: The connector class to register
            type_info: Metadata about the connector type
        """
        if subtype in self._connectors:
            logger.warning(f"Overwriting existing connector for {subtype}")
        self._connectors[subtype] = connector_class
        self._type_info[subtype] = type_info
        logger.debug(f"Registered connector: {subtype}")

    def unregister(self, subtype: ConnectorSubtype) -> None:
        """Unregister a connector implementation.

        Args:
            subtype: The connector subtype to unregister
        """
        self._connectors.pop(subtype, None)
        self._type_info.pop(subtype, None)

    def get_connector_class(
        self, subtype: ConnectorSubtype
    ) -> Type[BaseConnector] | None:
        """Get the connector class for a subtype.

        Args:
            subtype: The connector subtype

        Returns:
            The connector class, or None if not registered
        """
        return self._connectors.get(subtype)

    def create_connector(
        self,
        subtype: ConnectorSubtype,
        connector_id: str,
        name: str,
        config: dict[str, Any],
        batch_size: int = 1000,
    ) -> BaseConnector:
        """Create a connector instance.

        Args:
            subtype: The connector subtype
            connector_id: Unique identifier for the connector
            name: Human-readable name
            config: Connection configuration
            batch_size: Batch size for extraction

        Returns:
            Instantiated connector

        Raises:
            ValueError: If subtype is not registered
        """
        connector_class = self._connectors.get(subtype)
        if connector_class is None:
            raise ValueError(f"No connector registered for subtype: {subtype}")

        return connector_class(
            connector_id=connector_id,
            name=name,
            config=config,
            batch_size=batch_size,
        )

    def get_type_info(self, subtype: ConnectorSubtype) -> ConnectorTypeInfo | None:
        """Get type information for a connector subtype.

        Args:
            subtype: The connector subtype

        Returns:
            ConnectorTypeInfo or None if not registered
        """
        return self._type_info.get(subtype)

    def list_types(self) -> list[ConnectorTypeInfo]:
        """List all registered connector types.

        Returns:
            List of ConnectorTypeInfo for all registered types
        """
        return list(self._type_info.values())

    def list_types_by_category(
        self, connector_type: ConnectorType
    ) -> list[ConnectorTypeInfo]:
        """List connector types by category.

        Args:
            connector_type: DATABASE, API, or FILE

        Returns:
            List of ConnectorTypeInfo for the category
        """
        return [
            info for info in self._type_info.values() if info.type == connector_type
        ]

    def is_registered(self, subtype: ConnectorSubtype) -> bool:
        """Check if a connector subtype is registered.

        Args:
            subtype: The connector subtype

        Returns:
            True if registered
        """
        return subtype in self._connectors


# Global registry instance
_registry = ConnectorRegistry()


def get_registry() -> ConnectorRegistry:
    """Get the global connector registry.

    Returns:
        The global ConnectorRegistry instance
    """
    return _registry


def register_connector(
    subtype: ConnectorSubtype,
    connector_class: Type[BaseConnector],
    name: str,
    description: str,
    connector_type: ConnectorType,
    config_schema: dict[str, Any],
    supported_data_types: list[DataType] | None = None,
) -> None:
    """Convenience function to register a connector.

    Args:
        subtype: The connector subtype
        connector_class: The connector class to register
        name: Human-readable name
        description: Description of the connector
        connector_type: DATABASE, API, or FILE
        config_schema: JSON Schema for connection configuration
        supported_data_types: List of supported data types (default: all)
    """
    if supported_data_types is None:
        supported_data_types = list(DataType)

    type_info = ConnectorTypeInfo(
        type=connector_type,
        subtype=subtype,
        name=name,
        description=description,
        config_schema=config_schema,
        supported_data_types=supported_data_types,
    )
    _registry.register(subtype, connector_class, type_info)


def create_connector(
    subtype: ConnectorSubtype,
    connector_id: str,
    name: str,
    config: dict[str, Any],
    batch_size: int = 1000,
) -> BaseConnector:
    """Convenience function to create a connector instance.

    Args:
        subtype: The connector subtype
        connector_id: Unique identifier
        name: Human-readable name
        config: Connection configuration
        batch_size: Batch size for extraction

    Returns:
        Instantiated connector
    """
    return _registry.create_connector(subtype, connector_id, name, config, batch_size)


def get_connector_info(subtype: ConnectorSubtype) -> ConnectorTypeInfo | None:
    """Get type information for a connector subtype.

    Args:
        subtype: The connector subtype

    Returns:
        ConnectorTypeInfo or None if not registered
    """
    return _registry.get_type_info(subtype)


def list_connector_types() -> list[ConnectorTypeInfo]:
    """List all registered connector types.

    Returns:
        List of ConnectorTypeInfo for all registered types
    """
    return _registry.list_types()
