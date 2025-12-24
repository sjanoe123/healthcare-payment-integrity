"""Configuration file loader for connectors.

Supports loading connector configurations from YAML and JSON files,
enabling infrastructure-as-code patterns for data source management.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .models import (
    ConnectorCreate,
    ConnectorSubtype,
    ConnectorType,
    DataType,
    SyncMode,
)
from .registry import get_connector_info

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.errors = errors or []


class ConfigLoader:
    """Loads and validates connector configurations from files."""

    def __init__(self, config_dir: str | Path | None = None):
        """Initialize the config loader.

        Args:
            config_dir: Directory containing config files.
                        Defaults to ./config/connectors/
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path("config/connectors")

    def load_file(self, file_path: str | Path) -> list[ConnectorCreate]:
        """Load connector configurations from a single file.

        Args:
            file_path: Path to YAML or JSON config file

        Returns:
            List of ConnectorCreate models

        Raises:
            ConfigValidationError: If validation fails
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        # Detect format from extension
        suffix = path.suffix.lower()

        if suffix in (".yaml", ".yml"):
            return self._load_yaml(path)
        elif suffix == ".json":
            return self._load_json(path)
        else:
            raise ValueError(f"Unsupported config format: {suffix}")

    def load_directory(
        self, directory: str | Path | None = None
    ) -> list[ConnectorCreate]:
        """Load all connector configurations from a directory.

        Args:
            directory: Directory to scan. Defaults to self.config_dir.

        Returns:
            List of ConnectorCreate models from all files

        Raises:
            ConfigValidationError: If any validation fails
        """
        config_dir = Path(directory) if directory else self.config_dir

        if not config_dir.exists():
            logger.warning(f"Config directory does not exist: {config_dir}")
            return []

        connectors = []
        errors = []

        # Process all YAML and JSON files
        for pattern in ("*.yaml", "*.yml", "*.json"):
            for file_path in config_dir.glob(pattern):
                try:
                    file_connectors = self.load_file(file_path)
                    connectors.extend(file_connectors)
                    logger.info(
                        f"Loaded {len(file_connectors)} connector(s) from {file_path.name}"
                    )
                except ConfigValidationError as e:
                    errors.extend(e.errors)
                except Exception as e:
                    errors.append(
                        {
                            "file": str(file_path),
                            "error": str(e),
                        }
                    )

        if errors:
            raise ConfigValidationError(
                f"Validation failed for {len(errors)} item(s)",
                errors=errors,
            )

        return connectors

    def _load_yaml(self, path: Path) -> list[ConnectorCreate]:
        """Load YAML configuration file.

        Args:
            path: Path to YAML file

        Returns:
            List of ConnectorCreate models
        """
        with open(path) as f:
            data = yaml.safe_load(f)

        return self._parse_config(data, str(path))

    def _load_json(self, path: Path) -> list[ConnectorCreate]:
        """Load JSON configuration file.

        Args:
            path: Path to JSON file

        Returns:
            List of ConnectorCreate models
        """
        with open(path) as f:
            data = json.load(f)

        return self._parse_config(data, str(path))

    def _parse_config(
        self, data: dict[str, Any] | list[dict[str, Any]], source: str
    ) -> list[ConnectorCreate]:
        """Parse configuration data into ConnectorCreate models.

        Args:
            data: Parsed YAML/JSON data
            source: Source file path for error messages

        Returns:
            List of ConnectorCreate models

        Raises:
            ConfigValidationError: If validation fails
        """
        # Handle both single connector and list of connectors
        if isinstance(data, dict):
            if "connectors" in data:
                # File contains a "connectors" array
                configs = data["connectors"]
            else:
                # File is a single connector config
                configs = [data]
        elif isinstance(data, list):
            configs = data
        else:
            raise ConfigValidationError(
                f"Invalid config format in {source}",
                errors=[{"file": source, "error": "Expected dict or list"}],
            )

        connectors = []
        errors = []

        for idx, config in enumerate(configs):
            try:
                connector = self._validate_connector_config(config, source, idx)
                connectors.append(connector)
            except ConfigValidationError as e:
                errors.extend(e.errors)
            except Exception as e:
                errors.append(
                    {
                        "file": source,
                        "index": idx,
                        "error": str(e),
                    }
                )

        if errors:
            raise ConfigValidationError(
                f"Validation failed for {len(errors)} connector(s) in {source}",
                errors=errors,
            )

        return connectors

    def _validate_connector_config(
        self, config: dict[str, Any], source: str, index: int
    ) -> ConnectorCreate:
        """Validate and convert a single connector configuration.

        Args:
            config: Raw connector config dict
            source: Source file for error messages
            index: Config index in file

        Returns:
            Validated ConnectorCreate model

        Raises:
            ConfigValidationError: If validation fails
        """
        errors = []

        # Required fields
        name = config.get("name")
        if not name:
            errors.append(
                {
                    "file": source,
                    "index": index,
                    "field": "name",
                    "error": "Name is required",
                }
            )

        # Connector type
        connector_type_str = config.get("type", config.get("connector_type"))
        try:
            connector_type = ConnectorType(connector_type_str)
        except (ValueError, TypeError):
            errors.append(
                {
                    "file": source,
                    "index": index,
                    "field": "type",
                    "error": f"Invalid type: {connector_type_str}. "
                    f"Valid: {[t.value for t in ConnectorType]}",
                }
            )
            connector_type = None

        # Subtype
        subtype_str = config.get("subtype")
        try:
            subtype = ConnectorSubtype(subtype_str)
        except (ValueError, TypeError):
            errors.append(
                {
                    "file": source,
                    "index": index,
                    "field": "subtype",
                    "error": f"Invalid subtype: {subtype_str}. "
                    f"Valid: {[s.value for s in ConnectorSubtype]}",
                }
            )
            subtype = None

        # Data type
        data_type_str = config.get("data_type")
        try:
            data_type = DataType(data_type_str)
        except (ValueError, TypeError):
            errors.append(
                {
                    "file": source,
                    "index": index,
                    "field": "data_type",
                    "error": f"Invalid data_type: {data_type_str}. "
                    f"Valid: {[d.value for d in DataType]}",
                }
            )
            data_type = None

        # Sync mode
        sync_mode_str = config.get("sync_mode", "incremental")
        try:
            sync_mode = SyncMode(sync_mode_str)
        except (ValueError, TypeError):
            errors.append(
                {
                    "file": source,
                    "index": index,
                    "field": "sync_mode",
                    "error": f"Invalid sync_mode: {sync_mode_str}. "
                    f"Valid: {[s.value for s in SyncMode]}",
                }
            )
            sync_mode = SyncMode.INCREMENTAL

        # Connection config
        connection_config = config.get(
            "connection", config.get("connection_config", {})
        )
        if not connection_config:
            errors.append(
                {
                    "file": source,
                    "index": index,
                    "field": "connection",
                    "error": "Connection configuration is required",
                }
            )

        # Validate connection config against connector schema
        if subtype and connection_config:
            try:
                connector_info = get_connector_info(subtype)
                if connector_info:
                    schema_errors = self._validate_connection_config(
                        connection_config,
                        connector_info.config_schema,
                        source,
                        index,
                    )
                    errors.extend(schema_errors)
            except Exception as e:
                logger.warning(f"Could not validate against schema: {e}")

        if errors:
            raise ConfigValidationError(
                f"Validation failed for connector '{name}'",
                errors=errors,
            )

        # Build ConnectorCreate model
        return ConnectorCreate(
            name=name,
            connector_type=connector_type,  # type: ignore
            subtype=subtype,  # type: ignore
            data_type=data_type,  # type: ignore
            connection_config=connection_config,
            sync_schedule=config.get("schedule", config.get("sync_schedule")),
            sync_mode=sync_mode,
            batch_size=config.get("batch_size", 1000),
            field_mapping_id=config.get("field_mapping_id"),
            created_by=config.get("created_by", "config_loader"),
        )

    def _validate_connection_config(
        self,
        config: dict[str, Any],
        schema: dict[str, Any],
        source: str,
        index: int,
    ) -> list[dict[str, Any]]:
        """Validate connection config against JSON schema.

        Args:
            config: Connection configuration
            schema: JSON schema for validation
            source: Source file for error messages
            index: Config index in file

        Returns:
            List of validation errors
        """
        errors = []

        # Check required fields
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field in required:
            if field not in config or config[field] is None:
                errors.append(
                    {
                        "file": source,
                        "index": index,
                        "field": f"connection.{field}",
                        "error": f"Required field missing: {field}",
                    }
                )

        # Basic type validation
        for field, value in config.items():
            if field in properties:
                prop_schema = properties[field]
                expected_type = prop_schema.get("type")

                if expected_type == "string" and not isinstance(value, str):
                    if value is not None:
                        errors.append(
                            {
                                "file": source,
                                "index": index,
                                "field": f"connection.{field}",
                                "error": f"Expected string, got {type(value).__name__}",
                            }
                        )
                elif expected_type == "integer" and not isinstance(value, int):
                    if value is not None:
                        errors.append(
                            {
                                "file": source,
                                "index": index,
                                "field": f"connection.{field}",
                                "error": f"Expected integer, got {type(value).__name__}",
                            }
                        )
                elif expected_type == "boolean" and not isinstance(value, bool):
                    if value is not None:
                        errors.append(
                            {
                                "file": source,
                                "index": index,
                                "field": f"connection.{field}",
                                "error": f"Expected boolean, got {type(value).__name__}",
                            }
                        )

                # Enum validation
                enum_values = prop_schema.get("enum")
                if enum_values and value not in enum_values:
                    errors.append(
                        {
                            "file": source,
                            "index": index,
                            "field": f"connection.{field}",
                            "error": f"Invalid value: {value}. Valid: {enum_values}",
                        }
                    )

                # Range validation
                minimum = prop_schema.get("minimum")
                maximum = prop_schema.get("maximum")
                if minimum is not None and isinstance(value, (int, float)):
                    if value < minimum:
                        errors.append(
                            {
                                "file": source,
                                "index": index,
                                "field": f"connection.{field}",
                                "error": f"Value {value} is below minimum {minimum}",
                            }
                        )
                if maximum is not None and isinstance(value, (int, float)):
                    if value > maximum:
                        errors.append(
                            {
                                "file": source,
                                "index": index,
                                "field": f"connection.{field}",
                                "error": f"Value {value} exceeds maximum {maximum}",
                            }
                        )

        return errors

    def export_config(
        self,
        connectors: list[dict[str, Any]],
        output_path: str | Path,
        format: str = "yaml",
    ) -> None:
        """Export connector configurations to a file.

        Args:
            connectors: List of connector configurations
            output_path: Output file path
            format: Output format ("yaml" or "json")
        """
        path = Path(output_path)

        # Prepare export data
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "connectors": connectors,
        }

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        if format == "yaml":
            with open(path, "w") as f:
                yaml.dump(export_data, f, default_flow_style=False, sort_keys=False)
        elif format == "json":
            with open(path, "w") as f:
                json.dump(export_data, f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported {len(connectors)} connector(s) to {path}")


def load_connectors_from_config(
    config_dir: str | Path | None = None,
) -> list[ConnectorCreate]:
    """Convenience function to load connectors from config directory.

    Args:
        config_dir: Directory containing config files

    Returns:
        List of ConnectorCreate models
    """
    loader = ConfigLoader(config_dir)
    return loader.load_directory()


# Example configuration templates
EXAMPLE_POSTGRESQL_CONFIG = """
# PostgreSQL Data Source Configuration
name: claims_database
type: database
subtype: postgresql
data_type: claims
sync_mode: incremental
schedule: "0 */6 * * *"  # Every 6 hours
batch_size: 5000

connection:
  host: db.example.com
  port: 5432
  database: healthcare
  username: readonly_user
  password: "${POSTGRES_PASSWORD}"  # Use environment variable
  ssl_mode: require
  schema_name: public
  table: claims
  watermark_column: modified_at
"""

EXAMPLE_S3_CONFIG = """
# AWS S3 Data Source Configuration
name: claims_files
type: file
subtype: s3
data_type: claims
sync_mode: incremental
schedule: "0 2 * * *"  # Daily at 2 AM

connection:
  bucket: healthcare-claims-bucket
  region: us-east-1
  prefix: incoming/edi/
  path_pattern: "*.edi"
  file_format: edi_837
  archive_processed: true
  archive_path: processed/
"""

EXAMPLE_FHIR_CONFIG = """
# FHIR API Data Source Configuration
name: hospital_fhir
type: api
subtype: fhir
data_type: claims
sync_mode: incremental
schedule: "0 */4 * * *"  # Every 4 hours

connection:
  base_url: https://fhir.hospital.example.com/r4
  auth_type: oauth2
  oauth2_config:
    token_url: https://auth.hospital.example.com/oauth2/token
    client_id: "${FHIR_CLIENT_ID}"
    client_secret: "${FHIR_CLIENT_SECRET}"
    scope: "system/*.read"
  resource_types:
    - Claim
    - ExplanationOfBenefit
  timeout: 60
  rate_limit: 10
"""
