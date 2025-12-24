"""Transform stage for ETL pipeline.

Handles data transformation including:
- Field mapping and renaming
- Data type conversions
- Value normalization
- OMOP CDM mapping integration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class TransformationResult:
    """Result from a transformation operation."""

    records: list[dict[str, Any]]
    transformed_count: int
    failed_count: int
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FieldMapping:
    """Configuration for mapping a source field to target."""

    source_field: str
    target_field: str
    transform: Callable[[Any], Any] | None = None
    default_value: Any = None
    required: bool = False


class TransformStage:
    """Transform stage for data normalization and mapping.

    Applies field mappings, data type conversions, and
    integrates with the existing mapping module for OMOP CDM.
    """

    def __init__(
        self,
        field_mappings: list[FieldMapping] | None = None,
        mapping_id: str | None = None,
        data_type: str | None = None,
    ) -> None:
        """Initialize the transform stage.

        Args:
            field_mappings: List of field mapping configurations
            mapping_id: ID of saved mapping from mapping module
            data_type: Data type (claims, eligibility, providers)
        """
        self.field_mappings = field_mappings or []
        self.mapping_id = mapping_id
        self.data_type = data_type
        self._loaded_mapping: dict[str, Any] | None = None

    def load_mapping(self) -> None:
        """Load mapping configuration from database."""
        if self.mapping_id:
            try:
                from ...mapping.persistence import MappingPersistence

                persistence = MappingPersistence()
                self._loaded_mapping = persistence.get_mapping(self.mapping_id)
                if self._loaded_mapping:
                    # Convert to field mappings
                    self._build_field_mappings_from_saved()
                    logger.info(f"Loaded mapping: {self.mapping_id}")
            except Exception as e:
                logger.warning(f"Could not load mapping {self.mapping_id}: {e}")

    def _build_field_mappings_from_saved(self) -> None:
        """Build field mappings from saved mapping configuration."""
        if not self._loaded_mapping:
            return

        mapping_config = self._loaded_mapping.get("mapping_config", {})
        field_maps = mapping_config.get("field_maps", {})

        for target_field, source_config in field_maps.items():
            if isinstance(source_config, str):
                # Simple field mapping
                self.field_mappings.append(
                    FieldMapping(
                        source_field=source_config,
                        target_field=target_field,
                    )
                )
            elif isinstance(source_config, dict):
                # Complex mapping with transform
                self.field_mappings.append(
                    FieldMapping(
                        source_field=source_config.get("source", ""),
                        target_field=target_field,
                        default_value=source_config.get("default"),
                        required=source_config.get("required", False),
                    )
                )

    def transform(
        self,
        records: list[dict[str, Any]],
        on_error: Callable[[dict[str, Any], Exception], None] | None = None,
    ) -> TransformationResult:
        """Transform a batch of records.

        Args:
            records: Source records to transform
            on_error: Optional callback for transformation errors

        Returns:
            TransformationResult with transformed records
        """
        # Load mapping if not already loaded
        if self.mapping_id and not self._loaded_mapping:
            self.load_mapping()

        transformed = []
        failed = 0
        errors = []

        for idx, record in enumerate(records):
            try:
                transformed_record = self._transform_record(record)
                transformed.append(transformed_record)
            except Exception as e:
                failed += 1
                error_info = {
                    "record_index": idx,
                    "error": str(e),
                    "record_preview": self._preview_record(record),
                }
                errors.append(error_info)

                if on_error:
                    on_error(record, e)

                logger.debug(f"Transform error at index {idx}: {e}")

        return TransformationResult(
            records=transformed,
            transformed_count=len(transformed),
            failed_count=failed,
            errors=errors,
        )

    def _transform_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Transform a single record.

        Args:
            record: Source record

        Returns:
            Transformed record
        """
        if not self.field_mappings:
            # No mappings - pass through with basic normalization
            return self._normalize_values(record)

        result = {}

        for mapping in self.field_mappings:
            value = record.get(mapping.source_field, mapping.default_value)

            # Check required fields
            if mapping.required and value is None:
                raise ValueError(f"Required field {mapping.source_field} is missing")

            # Apply transform if provided
            if mapping.transform and value is not None:
                value = mapping.transform(value)

            # Normalize value
            value = self._normalize_value(value)

            result[mapping.target_field] = value

        # Add unmapped fields if no strict mapping
        if not self.mapping_id:
            for key, value in record.items():
                if key not in [m.source_field for m in self.field_mappings]:
                    if key not in result:
                        result[key] = self._normalize_value(value)

        return result

    def _normalize_values(self, record: dict[str, Any]) -> dict[str, Any]:
        """Normalize all values in a record.

        Args:
            record: Source record

        Returns:
            Record with normalized values
        """
        return {key: self._normalize_value(value) for key, value in record.items()}

    def _normalize_value(self, value: Any) -> Any:
        """Normalize a single value.

        Args:
            value: Value to normalize

        Returns:
            Normalized value
        """
        if value is None:
            return None

        # Handle datetime objects
        if isinstance(value, datetime):
            return value.isoformat()

        # Handle bytes
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.hex()

        # Handle decimals
        if hasattr(value, "is_finite"):  # Decimal
            return float(value)

        return value

    def _preview_record(
        self, record: dict[str, Any], max_fields: int = 5
    ) -> dict[str, Any]:
        """Create a preview of a record for error logging.

        Args:
            record: Full record
            max_fields: Maximum fields to include

        Returns:
            Truncated record preview
        """
        preview = {}
        for idx, (key, value) in enumerate(record.items()):
            if idx >= max_fields:
                preview["..."] = f"({len(record) - max_fields} more fields)"
                break
            preview[key] = str(value)[:100] if value else None
        return preview

    def add_mapping(
        self,
        source_field: str,
        target_field: str,
        transform: Callable[[Any], Any] | None = None,
        default_value: Any = None,
        required: bool = False,
    ) -> None:
        """Add a field mapping.

        Args:
            source_field: Source field name
            target_field: Target field name
            transform: Optional transform function
            default_value: Default if source is missing
            required: Whether field is required
        """
        self.field_mappings.append(
            FieldMapping(
                source_field=source_field,
                target_field=target_field,
                transform=transform,
                default_value=default_value,
                required=required,
            )
        )

    def clear_mappings(self) -> None:
        """Clear all field mappings."""
        self.field_mappings = []
        self._loaded_mapping = None


# Common transform functions
def to_uppercase(value: Any) -> str:
    """Convert to uppercase string."""
    return str(value).upper() if value else ""


def to_lowercase(value: Any) -> str:
    """Convert to lowercase string."""
    return str(value).lower() if value else ""


def trim_whitespace(value: Any) -> str:
    """Trim whitespace from string."""
    return str(value).strip() if value else ""


def to_date(value: Any, format: str = "%Y-%m-%d") -> str | None:
    """Convert to date string."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime(format)
    return str(value)


def to_decimal(value: Any, precision: int = 2) -> float | None:
    """Convert to decimal with precision."""
    if value is None:
        return None
    try:
        return round(float(value), precision)
    except (ValueError, TypeError):
        return None
