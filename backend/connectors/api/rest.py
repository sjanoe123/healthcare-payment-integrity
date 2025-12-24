"""Generic REST API connector.

Provides connectivity to REST APIs for extracting healthcare data
with support for pagination, filtering, and data transformation.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator

from ..base import SyncMode
from ..models import ConnectionTestResult, ConnectorSubtype, ConnectorType, DataType
from ..registry import register_connector
from .base_api import BaseAPIConnector, HTTPX_AVAILABLE

logger = logging.getLogger(__name__)


class RESTConnector(BaseAPIConnector):
    """Connector for generic REST APIs.

    Supports:
    - Multiple authentication methods (API key, Basic, Bearer, OAuth2)
    - Configurable pagination (offset, cursor, page number, link header)
    - JSON path extraction for nested data
    - Watermark-based incremental sync
    """

    def __init__(
        self,
        connector_id: str,
        name: str,
        config: dict[str, Any],
        batch_size: int = 100,
    ) -> None:
        """Initialize REST connector.

        Args:
            connector_id: Unique identifier
            name: Human-readable name
            config: REST API configuration with keys:
                - base_url: API base URL
                - endpoint: Data endpoint path
                - auth_type: Authentication type
                - pagination_type: offset, cursor, page, link_header, none
                - pagination_param: Parameter name for pagination
                - limit_param: Parameter name for limit
                - data_path: JSON path to records array (e.g., "data.items")
                - watermark_field: Field for incremental sync
                - watermark_param: Query param for watermark filter
                - total_path: JSON path to total count
                - next_cursor_path: JSON path to next cursor
            batch_size: Records per batch
        """
        super().__init__(connector_id, name, config, batch_size)

    def test_connection(self) -> ConnectionTestResult:
        """Test REST API connection."""
        result = super().test_connection()

        if result.success:
            # Try to access the configured endpoint
            try:
                endpoint = self.config.get("endpoint", "/")
                response = self._get(endpoint, params={"limit": 1})

                # Try to extract data
                data_path = self.config.get("data_path")
                if data_path:
                    records = self._extract_data_path(response.json(), data_path)
                    record_count = len(records) if isinstance(records, list) else 0
                else:
                    data = response.json()
                    record_count = len(data) if isinstance(data, list) else 1

                result.details["endpoint"] = endpoint
                result.details["sample_records"] = record_count

            except Exception as e:
                # Connection works but endpoint might need adjustment
                result.details["endpoint_warning"] = str(e)[:100]

        return result

    def extract(
        self,
        sync_mode: SyncMode,
        watermark_value: str | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        """Extract data from REST API.

        Args:
            sync_mode: Full or incremental sync
            watermark_value: Last sync watermark for incremental

        Yields:
            Batches of records
        """
        if not self._connected:
            self.connect()

        endpoint = self.config.get("endpoint", "/")
        pagination_type = self.config.get("pagination_type", "none")
        limit_param = self.config.get("limit_param", "limit")
        data_path = self.config.get("data_path")

        # Build base params
        params: dict[str, Any] = {
            limit_param: self.batch_size,
        }

        # Add watermark filter for incremental sync
        if sync_mode == SyncMode.INCREMENTAL and watermark_value:
            watermark_param = self.config.get("watermark_param", "since")
            params[watermark_param] = watermark_value

        # Add any static params from config
        static_params = self.config.get("params", {})
        params.update(static_params)

        total_extracted = 0

        if pagination_type == "none":
            # Single request
            response = self._get(endpoint, params=params)
            records = self._extract_records(response.json(), data_path)
            if records:
                yield records
                total_extracted += len(records)

        elif pagination_type == "offset":
            # Offset-based pagination
            offset_param = self.config.get("pagination_param", "offset")
            offset = 0

            while True:
                params[offset_param] = offset
                response = self._get(endpoint, params=params)
                data = response.json()

                records = self._extract_records(data, data_path)
                if not records:
                    break

                yield records
                total_extracted += len(records)
                offset += len(records)

                # Check if we've reached the end
                total_path = self.config.get("total_path")
                if total_path:
                    total = self._extract_data_path(data, total_path)
                    if isinstance(total, int) and offset >= total:
                        break

                if len(records) < self.batch_size:
                    break

        elif pagination_type == "page":
            # Page-based pagination
            page_param = self.config.get("pagination_param", "page")
            page = 1

            while True:
                params[page_param] = page
                response = self._get(endpoint, params=params)
                data = response.json()

                records = self._extract_records(data, data_path)
                if not records:
                    break

                yield records
                total_extracted += len(records)
                page += 1

                if len(records) < self.batch_size:
                    break

        elif pagination_type == "cursor":
            # Cursor-based pagination
            cursor_param = self.config.get("pagination_param", "cursor")
            next_cursor_path = self.config.get("next_cursor_path", "next_cursor")
            cursor: str | None = None

            while True:
                if cursor:
                    params[cursor_param] = cursor

                response = self._get(endpoint, params=params)
                data = response.json()

                records = self._extract_records(data, data_path)
                if not records:
                    break

                yield records
                total_extracted += len(records)

                # Get next cursor
                cursor = self._extract_data_path(data, next_cursor_path)
                if not cursor:
                    break

        elif pagination_type == "link_header":
            # Link header pagination (RFC 5988)
            url = endpoint

            while url:
                response = self._get(url, params=params if url == endpoint else None)
                data = response.json()

                records = self._extract_records(data, data_path)
                if not records:
                    break

                yield records
                total_extracted += len(records)

                # Parse Link header for next URL
                url = self._parse_link_header(response.headers.get("Link", ""))

        self._log("info", f"Extracted {total_extracted} records from REST API")

    def _extract_records(
        self, data: Any, data_path: str | None
    ) -> list[dict[str, Any]]:
        """Extract records from response data.

        Args:
            data: Response JSON data
            data_path: JSON path to records array

        Returns:
            List of record dictionaries
        """
        if data_path:
            records = self._extract_data_path(data, data_path)
        else:
            records = data

        if isinstance(records, list):
            return [r for r in records if isinstance(r, dict)]
        elif isinstance(records, dict):
            return [records]
        return []

    def _extract_data_path(self, data: Any, path: str) -> Any:
        """Extract value from nested data using dot notation.

        Args:
            data: Source data
            path: Dot-notation path (e.g., "data.items")

        Returns:
            Extracted value or None
        """
        if not path:
            return data

        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None

        return current

    def _parse_link_header(self, link_header: str) -> str | None:
        """Parse RFC 5988 Link header for next URL.

        Args:
            link_header: Link header value

        Returns:
            Next URL or None
        """
        if not link_header:
            return None

        for link in link_header.split(","):
            parts = link.strip().split(";")
            if len(parts) < 2:
                continue

            url = parts[0].strip()
            if url.startswith("<") and url.endswith(">"):
                url = url[1:-1]

            for part in parts[1:]:
                part = part.strip()
                if part.lower() == 'rel="next"' or part.lower() == "rel=next":
                    return url

        return None

    def discover_schema(self) -> dict[str, Any]:
        """Discover API schema by sampling data.

        Returns:
            Schema information with fields and types
        """
        if not self._connected:
            self.connect()

        endpoint = self.config.get("endpoint", "/")
        limit_param = self.config.get("limit_param", "limit")
        data_path = self.config.get("data_path")

        try:
            response = self._get(endpoint, params={limit_param: 10})
            data = response.json()
            records = self._extract_records(data, data_path)

            if not records:
                return {"fields": [], "sample_count": 0}

            # Analyze fields from sample records
            fields: dict[str, dict[str, Any]] = {}

            for record in records:
                for key, value in record.items():
                    if key not in fields:
                        fields[key] = {
                            "name": key,
                            "types": set(),
                            "nullable": False,
                            "sample_values": [],
                        }

                    # Track type
                    value_type = type(value).__name__
                    fields[key]["types"].add(value_type)

                    if value is None:
                        fields[key]["nullable"] = True
                    elif len(fields[key]["sample_values"]) < 3:
                        fields[key]["sample_values"].append(str(value)[:50])

            # Convert to list format
            field_list = []
            for name, info in fields.items():
                field_list.append(
                    {
                        "name": name,
                        "type": self._infer_type(info["types"]),
                        "nullable": info["nullable"],
                        "sample_values": info["sample_values"],
                    }
                )

            return {
                "fields": field_list,
                "sample_count": len(records),
                "endpoint": endpoint,
            }

        except Exception as e:
            logger.error(f"Schema discovery failed: {e}")
            return {"fields": [], "error": str(e)}

    def _infer_type(self, types: set[str]) -> str:
        """Infer field type from observed types.

        Args:
            types: Set of observed type names

        Returns:
            Inferred type string
        """
        types = types - {"NoneType"}

        if not types:
            return "string"
        if len(types) == 1:
            t = types.pop()
            type_map = {
                "str": "string",
                "int": "integer",
                "float": "number",
                "bool": "boolean",
                "list": "array",
                "dict": "object",
            }
            return type_map.get(t, "string")
        if types == {"int", "float"}:
            return "number"
        return "string"


# Configuration schema for the UI
REST_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["base_url", "endpoint"],
    "properties": {
        "base_url": {
            "type": "string",
            "title": "Base URL",
            "description": "API base URL (e.g., https://api.example.com)",
        },
        "endpoint": {
            "type": "string",
            "title": "Data Endpoint",
            "description": "Path to data endpoint (e.g., /v1/claims)",
            "default": "/",
        },
        "auth_type": {
            "type": "string",
            "title": "Authentication",
            "description": "Authentication method",
            "enum": ["none", "api_key", "basic", "bearer", "oauth2"],
            "default": "none",
        },
        "api_key": {
            "type": "string",
            "title": "API Key",
            "description": "API key for authentication",
            "format": "password",
        },
        "api_key_header": {
            "type": "string",
            "title": "API Key Header",
            "description": "Header name for API key",
            "default": "X-API-Key",
        },
        "username": {
            "type": "string",
            "title": "Username",
            "description": "Username for Basic auth",
        },
        "password": {
            "type": "string",
            "title": "Password",
            "description": "Password for Basic auth",
            "format": "password",
        },
        "bearer_token": {
            "type": "string",
            "title": "Bearer Token",
            "description": "Bearer token for authentication",
            "format": "password",
        },
        "oauth2_config": {
            "type": "object",
            "title": "OAuth2 Configuration",
            "properties": {
                "token_url": {"type": "string", "title": "Token URL"},
                "client_id": {"type": "string", "title": "Client ID"},
                "client_secret": {
                    "type": "string",
                    "title": "Client Secret",
                    "format": "password",
                },
                "scope": {"type": "string", "title": "Scope"},
                "grant_type": {
                    "type": "string",
                    "title": "Grant Type",
                    "enum": ["client_credentials", "password", "refresh_token"],
                    "default": "client_credentials",
                },
            },
        },
        "pagination_type": {
            "type": "string",
            "title": "Pagination Type",
            "description": "How API handles pagination",
            "enum": ["none", "offset", "page", "cursor", "link_header"],
            "default": "none",
        },
        "pagination_param": {
            "type": "string",
            "title": "Pagination Parameter",
            "description": "Query param for pagination (offset, page, cursor)",
            "default": "offset",
        },
        "limit_param": {
            "type": "string",
            "title": "Limit Parameter",
            "description": "Query param for page size",
            "default": "limit",
        },
        "data_path": {
            "type": "string",
            "title": "Data Path",
            "description": "JSON path to records array (e.g., data.items)",
        },
        "watermark_field": {
            "type": "string",
            "title": "Watermark Field",
            "description": "Field for tracking incremental updates",
        },
        "watermark_param": {
            "type": "string",
            "title": "Watermark Parameter",
            "description": "Query param for watermark filter",
            "default": "since",
        },
        "timeout": {
            "type": "integer",
            "title": "Timeout (seconds)",
            "description": "Request timeout",
            "default": 30,
            "minimum": 5,
            "maximum": 300,
        },
        "rate_limit": {
            "type": "integer",
            "title": "Rate Limit (req/sec)",
            "description": "Maximum requests per second",
            "default": 10,
            "minimum": 1,
            "maximum": 100,
        },
        "verify_ssl": {
            "type": "boolean",
            "title": "Verify SSL",
            "description": "Verify SSL certificates",
            "default": True,
        },
    },
}


def _register_rest() -> None:
    """Register REST connector with the registry."""
    if not HTTPX_AVAILABLE:
        return

    register_connector(
        subtype=ConnectorSubtype.REST,
        connector_class=RESTConnector,
        name="REST API",
        description="Connect to REST APIs for healthcare data",
        connector_type=ConnectorType.API,
        config_schema=REST_CONFIG_SCHEMA,
        supported_data_types=[
            DataType.CLAIMS,
            DataType.ELIGIBILITY,
            DataType.PROVIDERS,
            DataType.REFERENCE,
        ],
    )


# Auto-register on import
_register_rest()
