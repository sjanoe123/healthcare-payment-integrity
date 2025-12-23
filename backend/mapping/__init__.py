"""Semantic schema mapping module for healthcare claims.

This module provides field mapping and normalization capabilities to transform
incoming healthcare claims from various formats (EDI 837P/I, CSV, payer-specific)
to a canonical OMOP CDM schema.

Usage:
    from mapping import FieldMapper, normalize_claim

    # Using the mapper class
    mapper = FieldMapper()
    normalized = mapper.transform(raw_claim)

    # Or use the convenience function
    normalized = normalize_claim(raw_claim)

    # With custom mappings
    custom = {"MemberIdentifier": "person_id"}
    normalized = normalize_claim(raw_claim, custom_mapping=custom)

    # With semantic (embedding-based) matching for unknown fields
    normalized = normalize_claim(raw_claim, use_semantic_matching=True)

    # Get semantic matches for review
    from mapping import normalize_claim_with_review
    normalized, semantic_matches = normalize_claim_with_review(raw_claim)

    # LLM reranking for confidence scoring
    from mapping import rerank_mapping, RerankerResult
    result = rerank_mapping("PatientMRN", [("person_id", 0.85)], ["MRN-123"])
"""

from .mapper import (
    FieldMapper,
    MappingResult,
    normalize_claim,
    normalize_claim_with_review,
)
from .omop_schema import (
    ALIAS_LOOKUP,
    OMOP_CLAIMS_SCHEMA,
    REQUIRED_FIELDS,
    OMOPField,
    get_all_aliases,
    get_required_fields,
)
from .reranker import (
    HIGH_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    MappingReranker,
    RerankerResult,
    get_reranker,
    rerank_mapping,
)
from .persistence import (
    AuditLogEntry,
    FieldMappingEntry,
    MappingAction,
    MappingStatus,
    MappingStore,
    SchemaMapping,
    get_mapping_store,
)

__all__ = [
    # Mapper
    "FieldMapper",
    "MappingResult",
    "normalize_claim",
    "normalize_claim_with_review",
    # Schema
    "OMOP_CLAIMS_SCHEMA",
    "ALIAS_LOOKUP",
    "REQUIRED_FIELDS",
    "OMOPField",
    "get_all_aliases",
    "get_required_fields",
    # Reranker
    "MappingReranker",
    "RerankerResult",
    "get_reranker",
    "rerank_mapping",
    "HIGH_CONFIDENCE_THRESHOLD",
    "LOW_CONFIDENCE_THRESHOLD",
    # Persistence
    "MappingStore",
    "SchemaMapping",
    "FieldMappingEntry",
    "AuditLogEntry",
    "MappingAction",
    "MappingStatus",
    "get_mapping_store",
]
