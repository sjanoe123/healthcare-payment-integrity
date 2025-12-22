"""Field mapper for transforming claims to OMOP CDM canonical schema.

This module provides the FieldMapper class that normalizes incoming claim data
from various formats (EDI 837P/I, CSV, payer-specific) to a canonical OMOP CDM
schema that the rules engine can process consistently.

Usage:
    mapper = FieldMapper()
    normalized = mapper.transform(raw_claim)
"""

from __future__ import annotations

import logging
from typing import Any

from .omop_schema import ALIAS_LOOKUP, OMOP_CLAIMS_SCHEMA

logger = logging.getLogger(__name__)


class MappingResult:
    """Result of a field mapping operation with confidence tracking."""

    def __init__(self) -> None:
        self.mapped_fields: dict[str, Any] = {}
        self.unmapped_fields: list[str] = []
        self.mapping_sources: dict[str, str] = {}  # canonical -> source field
        self.confidence_scores: dict[str, float] = {}

    def add_mapping(
        self,
        canonical: str,
        value: Any,
        source: str,
        confidence: float = 1.0,
    ) -> None:
        """Add a successful field mapping."""
        self.mapped_fields[canonical] = value
        self.mapping_sources[canonical] = source
        self.confidence_scores[canonical] = confidence

    def add_unmapped(self, field_name: str) -> None:
        """Track an unmapped field for later review."""
        if field_name not in self.unmapped_fields:
            self.unmapped_fields.append(field_name)


class FieldMapper:
    """Transforms incoming claim data to OMOP CDM canonical schema.

    The mapper uses a three-tier approach:
    1. Exact match on canonical field names
    2. Alias matching from the OMOP schema
    3. Custom mapping configuration (for client-specific overrides)

    Attributes:
        custom_mapping: Optional dictionary of custom field mappings
        strict_mode: If True, raise errors for missing required fields
    """

    def __init__(
        self,
        custom_mapping: dict[str, str] | None = None,
        strict_mode: bool = False,
        use_semantic_matching: bool = False,
        semantic_threshold: float = 0.7,
    ) -> None:
        """Initialize the field mapper.

        Args:
            custom_mapping: Optional dict mapping source fields to canonical names.
                           Example: {"MemberIdentifier": "person_id"}
            strict_mode: If True, raise ValueError for missing required fields.
            use_semantic_matching: If True, use embedding-based matching for
                                   unrecognized fields (requires sentence-transformers).
            semantic_threshold: Minimum similarity score for semantic matches (0.0-1.0).
        """
        self.custom_mapping = custom_mapping or {}
        self.strict_mode = strict_mode
        self.use_semantic_matching = use_semantic_matching
        self.semantic_threshold = semantic_threshold
        # Build a lowercase lookup for custom mappings: source_field.lower() -> canonical
        self._custom_lookup = {k.lower(): v for k, v in self.custom_mapping.items()}
        # Track semantic matches for review
        self._semantic_matches: dict[str, tuple[str, float]] = {}

    def transform(self, raw_claim: dict[str, Any]) -> dict[str, Any]:
        """Transform raw claim data to canonical OMOP CDM format.

        Args:
            raw_claim: Raw claim data in any supported format

        Returns:
            Normalized claim dictionary with OMOP CDM field names

        Raises:
            ValueError: If strict_mode is True and required fields are missing
        """
        result = MappingResult()

        # Flatten nested structures for easier mapping
        flat_data = self._flatten_dict(raw_claim)

        # Process each field in the input
        for source_field, value in flat_data.items():
            canonical = self._resolve_field(source_field)
            if canonical:
                result.add_mapping(canonical, value, source_field)
            else:
                result.add_unmapped(source_field)

        # Build the normalized output
        normalized = self._build_normalized_claim(result, raw_claim)

        # Log unmapped fields for debugging
        if result.unmapped_fields:
            logger.debug(
                "Unmapped fields in claim: %s",
                ", ".join(result.unmapped_fields[:10]),
            )

        # Strict mode validation
        if self.strict_mode:
            from .omop_schema import REQUIRED_FIELDS

            logger.debug(f"Validating required fields: {REQUIRED_FIELDS}")
            self._validate_required_fields(normalized)

        return normalized

    def _resolve_field(self, field_name: str) -> str | None:
        """Resolve a source field name to its canonical OMOP field.

        Uses a four-tier resolution strategy:
        1. Custom mapping (highest priority)
        2. Alias lookup from OMOP schema
        3. Case transformation (snake_case <-> camelCase)
        4. Semantic matching via embeddings (if enabled)

        Args:
            field_name: Source field name to resolve

        Returns:
            Canonical OMOP field name or None if not mappable
        """
        field_lower = field_name.lower()

        # 1. Check custom mapping first (highest priority)
        # custom_lookup maps source_field.lower() -> canonical
        if field_lower in self._custom_lookup:
            return self._custom_lookup[field_lower]

        # 2. Check exact match on canonical name or alias
        if field_lower in ALIAS_LOOKUP:
            return ALIAS_LOOKUP[field_lower]

        # 3. Try with common transformations
        # Handle snake_case <-> camelCase
        snake_version = self._to_snake_case(field_name)
        if snake_version.lower() in ALIAS_LOOKUP:
            return ALIAS_LOOKUP[snake_version.lower()]

        # 4. Semantic matching via embeddings (if enabled)
        if self.use_semantic_matching:
            return self._resolve_semantic(field_name)

        return None

    def _resolve_semantic(self, field_name: str) -> str | None:
        """Resolve field using embedding-based semantic matching.

        Args:
            field_name: Source field name to match semantically

        Returns:
            Best matching canonical field or None if below threshold
        """
        try:
            from .embeddings import get_embedding_matcher
        except ImportError:
            logger.warning(
                "Semantic matching unavailable: sentence-transformers not installed"
            )
            return None

        matcher = get_embedding_matcher()
        match = matcher.find_best_match(
            field_name, min_similarity=self.semantic_threshold
        )

        if match:
            canonical, score = match
            # Track semantic match for potential review
            self._semantic_matches[field_name] = (canonical, score)
            logger.info(
                f"Semantic match: '{field_name}' -> '{canonical}' (score: {score:.3f})"
            )
            return canonical

        return None

    def get_semantic_matches(self) -> dict[str, tuple[str, float]]:
        """Get all semantic matches made during transformation.

        Returns:
            Dictionary mapping source fields to (canonical, score) tuples.
            These are matches that were resolved via embedding similarity
            rather than direct alias lookup.
        """
        return self._semantic_matches.copy()

    def clear_semantic_matches(self) -> None:
        """Clear tracked semantic matches."""
        self._semantic_matches.clear()

    def _flatten_dict(
        self,
        data: dict[str, Any],
        parent_key: str = "",
        sep: str = ".",
    ) -> dict[str, Any]:
        """Flatten nested dictionary for field resolution.

        Args:
            data: Nested dictionary to flatten
            parent_key: Prefix for nested keys
            sep: Separator between nested key levels

        Returns:
            Flattened dictionary with dot-notation keys
        """
        items: list[tuple[str, Any]] = []

        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key

            if isinstance(value, dict):
                # Recursively flatten nested dicts
                items.extend(self._flatten_dict(value, new_key, sep).items())
                # Also add leaf values without parent prefix for alias matching.
                # This allows matching both 'member.age' and 'age' for nested data,
                # enabling alias lookup on the leaf field name alone.
                for nested_key, nested_value in value.items():
                    if not isinstance(nested_value, dict | list):
                        items.append((nested_key, nested_value))
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                # Handle list of dicts (like items/line items)
                # Keep the list structure for items
                items.append((new_key, value))
            else:
                items.append((new_key, value))
                # Also add without parent prefix for alias matching.
                # This allows matching both 'claim.service_date' and 'service_date',
                # enabling alias lookup on the leaf field name alone.
                if parent_key:
                    items.append((key, value))

        return dict(items)

    def _build_normalized_claim(
        self,
        result: MappingResult,
        raw_claim: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the normalized claim structure from mapping results.

        Args:
            result: MappingResult with mapped fields
            raw_claim: Original raw claim for items extraction

        Returns:
            Structured normalized claim dictionary
        """
        normalized: dict[str, Any] = {}

        # Copy all successfully mapped fields
        for canonical, value in result.mapped_fields.items():
            normalized[canonical] = value

        # Handle nested structures
        normalized["member"] = self._extract_member(result, raw_claim)
        normalized["provider"] = self._extract_provider(result, raw_claim)
        normalized["items"] = self._extract_items(raw_claim)

        # Ensure claim-level fields are present
        if "visit_occurrence_id" not in normalized:
            normalized["visit_occurrence_id"] = raw_claim.get(
                "claim_id"
            ) or raw_claim.get("id")

        return normalized

    def _extract_member(
        self,
        result: MappingResult,
        raw_claim: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract member/patient information."""
        member: dict[str, Any] = {}

        # Try to get from result first, then raw claim
        member_fields = ["person_id", "birth_datetime", "gender_source_value", "age"]

        for field in member_fields:
            if field in result.mapped_fields:
                member[field] = result.mapped_fields[field]

        # Also check raw claim for nested member object
        raw_member = raw_claim.get("member", {})
        if raw_member:
            if "member_id" in raw_member and "person_id" not in member:
                member["person_id"] = raw_member["member_id"]
            if "age" in raw_member:
                member["age"] = raw_member["age"]
            if "gender" in raw_member:
                member["gender_source_value"] = raw_member["gender"]

        return member

    def _extract_provider(
        self,
        result: MappingResult,
        raw_claim: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract provider information."""
        provider: dict[str, Any] = {}

        provider_fields = ["npi", "specialty_source_value", "provider_id"]

        for field in provider_fields:
            if field in result.mapped_fields:
                provider[field] = result.mapped_fields[field]

        # Also check raw claim for nested provider object
        raw_provider = raw_claim.get("provider", {})
        if raw_provider:
            if "npi" in raw_provider and "npi" not in provider:
                provider["npi"] = raw_provider["npi"]
            if "specialty" in raw_provider:
                provider["specialty_source_value"] = raw_provider["specialty"]

        return provider

    def _extract_items(self, raw_claim: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract and normalize line items/procedures."""
        raw_items = raw_claim.get("items", [])
        if not raw_items:
            return []

        normalized_items: list[dict[str, Any]] = []

        for item in raw_items:
            if not isinstance(item, dict):
                continue

            normalized_item: dict[str, Any] = {}

            # Map item fields
            item_mappings = {
                "procedure_code": "procedure_source_value",
                "cpt_code": "procedure_source_value",
                "hcpcs_code": "procedure_source_value",
                "quantity": "quantity",
                "units": "quantity",
                "modifier": "modifier_source_value",
                "modifier_1": "modifier_source_value",
                "line_amount": "line_charge",
                "charge_amount": "line_charge",
                "diagnosis_code": "condition_source_value",
            }

            for source_key, canonical_key in item_mappings.items():
                if source_key in item and canonical_key not in normalized_item:
                    normalized_item[canonical_key] = item[source_key]

            # Copy any already-canonical fields
            for key, value in item.items():
                if key in OMOP_CLAIMS_SCHEMA and key not in normalized_item:
                    normalized_item[key] = value

            if normalized_item:
                normalized_items.append(normalized_item)

        return normalized_items

    def _validate_required_fields(self, normalized: dict[str, Any]) -> None:
        """Validate that required fields are present.

        Args:
            normalized: Normalized claim dictionary

        Raises:
            ValueError: If required fields are missing
        """
        from .omop_schema import REQUIRED_FIELDS

        missing = []
        for field in REQUIRED_FIELDS:
            if field not in normalized or normalized[field] is None:
                # Check nested structures
                if field == "person_id" and normalized.get("member", {}).get(
                    "person_id"
                ):
                    continue
                if field == "npi" and normalized.get("provider", {}).get("npi"):
                    continue
                missing.append(field)

        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert camelCase or PascalCase to snake_case."""
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result)


def normalize_claim(
    raw_claim: dict[str, Any],
    custom_mapping: dict[str, str] | None = None,
    use_semantic_matching: bool = False,
    semantic_threshold: float = 0.7,
) -> dict[str, Any]:
    """Convenience function to normalize a claim.

    Args:
        raw_claim: Raw claim data in any supported format
        custom_mapping: Optional custom field mappings
        use_semantic_matching: If True, use embedding-based matching for
                               unrecognized fields (requires sentence-transformers).
        semantic_threshold: Minimum similarity score for semantic matches (0.0-1.0).

    Returns:
        Normalized claim dictionary with OMOP CDM field names
    """
    mapper = FieldMapper(
        custom_mapping=custom_mapping,
        use_semantic_matching=use_semantic_matching,
        semantic_threshold=semantic_threshold,
    )
    return mapper.transform(raw_claim)


def normalize_claim_with_review(
    raw_claim: dict[str, Any],
    custom_mapping: dict[str, str] | None = None,
    semantic_threshold: float = 0.7,
) -> tuple[dict[str, Any], dict[str, tuple[str, float]]]:
    """Normalize a claim and return semantic matches for review.

    This function enables semantic matching and returns both the normalized
    claim and a dictionary of semantic matches for human review.

    Args:
        raw_claim: Raw claim data in any supported format
        custom_mapping: Optional custom field mappings
        semantic_threshold: Minimum similarity score for semantic matches

    Returns:
        Tuple of (normalized_claim, semantic_matches) where semantic_matches
        is a dict mapping source fields to (canonical, score) tuples.
    """
    mapper = FieldMapper(
        custom_mapping=custom_mapping,
        use_semantic_matching=True,
        semantic_threshold=semantic_threshold,
    )
    normalized = mapper.transform(raw_claim)
    return normalized, mapper.get_semantic_matches()
