"""Field mapping routes for OMOP CDM normalization.

This router handles semantic field matching, mapping preview,
persistence, and approval workflows.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from config import DB_PATH

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mappings", tags=["mappings"])


# Request/Response Models
class MappingPreviewRequest(BaseModel):
    sample_data: dict[str, Any]
    template: str | None = None


class SemanticMatchRequest(BaseModel):
    source_fields: list[str]
    top_k: int = 5
    min_similarity: float = 0.3

    @field_validator("source_fields")
    @classmethod
    def validate_source_fields_length(cls, v: list[str]) -> list[str]:
        """Validate that source_fields doesn't exceed maximum length."""
        if len(v) > 100:
            raise ValueError("Too many fields. Maximum 100 per request.")
        return v


class SemanticPreviewRequest(BaseModel):
    sample_data: dict[str, Any]
    template: str | None = None
    use_semantic: bool = True
    semantic_threshold: float = 0.7


class SaveMappingRequest(BaseModel):
    """Request model for saving a mapping."""

    source_schema_id: str
    field_mappings: list[dict[str, Any]]
    created_by: str | None = None


class ApproveMappingRequest(BaseModel):
    """Request model for approving a mapping."""

    approved_by: str


class RejectMappingRequest(BaseModel):
    """Request model for rejecting a mapping."""

    rejected_by: str
    reason: str | None = None


# Routes
@router.get("/templates")
async def list_mapping_templates():
    """List available field mapping templates."""
    return {
        "templates": [
            {
                "name": "edi_837p",
                "description": "EDI 837P Professional Claims (CMS-1500)",
                "claim_types": ["professional"],
            },
            {
                "name": "edi_837i",
                "description": "EDI 837I Institutional Claims (UB-04)",
                "claim_types": ["institutional", "hospital"],
            },
            {
                "name": "csv",
                "description": "Generic CSV field naming conventions",
                "claim_types": ["all"],
            },
        ],
        "default": "alias-based mapping (no template required)",
    }


@router.post("/preview")
async def preview_mapping(request: MappingPreviewRequest):
    """Preview how sample data would be mapped to OMOP CDM schema."""
    from mapping import normalize_claim
    from mapping.templates import get_template

    custom_mapping = None
    template_used = "alias-based (default)"

    if request.template:
        try:
            custom_mapping = get_template(request.template)
            template_used = request.template
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    normalized = normalize_claim(request.sample_data, custom_mapping=custom_mapping)

    return {
        "template_used": template_used,
        "input_fields": list(request.sample_data.keys()),
        "normalized": normalized,
        "mapped_fields": [
            k for k, v in normalized.items() if v is not None and v != {} and v != []
        ],
    }


@router.get("/schema")
async def get_canonical_schema():
    """Get the canonical OMOP CDM schema definition."""
    from mapping.omop_schema import OMOP_CLAIMS_SCHEMA

    schema_info = {}
    for field_name, field_def in OMOP_CLAIMS_SCHEMA.items():
        schema_info[field_name] = {
            "type": field_def.field_type,
            "required": field_def.required,
            "aliases": field_def.aliases,
            "description": field_def.description,
        }

    return {
        "schema_name": "OMOP CDM v5.4 (Claims Subset)",
        "fields": schema_info,
        "reference": "https://ohdsi.github.io/CommonDataModel/",
    }


@router.post("/semantic")
async def find_semantic_matches(request: SemanticMatchRequest):
    """Find semantic matches for unknown field names using PubMedBERT embeddings."""
    try:
        from mapping.embeddings import get_embedding_matcher
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Semantic matching unavailable: sentence-transformers not installed",
        )

    matcher = get_embedding_matcher()

    if len(request.source_fields) == 1:
        candidates = matcher.find_candidates(
            request.source_fields[0],
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )
        return {
            "source_field": request.source_fields[0],
            "candidates": [
                {"canonical_field": field, "similarity": round(score, 4)}
                for field, score in candidates
            ],
        }
    else:
        all_results = matcher.batch_find_candidates(
            request.source_fields,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )
        return {
            "results": {
                source: [
                    {"canonical_field": field, "similarity": round(score, 4)}
                    for field, score in candidates
                ]
                for source, candidates in all_results.items()
            }
        }


@router.post("/preview/semantic")
async def preview_semantic_mapping(request: SemanticPreviewRequest):
    """Preview field mapping with semantic matching for unknown fields."""
    from mapping import normalize_claim_with_review
    from mapping.templates import get_template

    custom_mapping = None
    template_used = "alias-based (default)"

    if request.template:
        try:
            custom_mapping = get_template(request.template)
            template_used = request.template
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    try:
        normalized, semantic_matches = normalize_claim_with_review(
            request.sample_data,
            custom_mapping=custom_mapping,
            semantic_threshold=request.semantic_threshold,
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Semantic matching unavailable: sentence-transformers not installed",
        )

    return {
        "template_used": template_used,
        "input_fields": list(request.sample_data.keys()),
        "normalized": normalized,
        "mapped_fields": [
            k for k, v in normalized.items() if v is not None and v != {} and v != []
        ],
        "semantic_matches": {
            source: {"canonical": canonical, "similarity": round(score, 4)}
            for source, (canonical, score) in semantic_matches.items()
        },
        "requires_review": [
            source for source, (_, score) in semantic_matches.items() if score < 0.85
        ],
    }


# Note: rerank and smart endpoints need rate limiting from main app
# They remain in app.py since they use @limiter


@router.post("/save")
async def save_mapping(request: SaveMappingRequest):
    """Save a new schema mapping for review."""
    from mapping.persistence import get_mapping_store

    store = get_mapping_store(DB_PATH)
    mapping = store.save_mapping(
        source_schema_id=request.source_schema_id,
        field_mappings=request.field_mappings,
        created_by=request.created_by,
    )

    return {
        "mapping_id": mapping.id,
        "source_schema_id": mapping.source_schema_id,
        "version": mapping.source_schema_version,
        "status": mapping.status.value,
        "created_at": mapping.created_at,
    }


@router.get("/stored")
async def list_stored_mappings(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List stored schema mappings with optional status filter."""
    from mapping.persistence import MappingStatus, get_mapping_store

    store = get_mapping_store(DB_PATH)

    status_filter = None
    if status:
        try:
            status_filter = MappingStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: pending, approved, rejected, archived",
            )

    mappings = store.list_mappings(status=status_filter, limit=limit, offset=offset)

    return {
        "mappings": [m.to_dict() for m in mappings],
        "total": len(mappings),
        "limit": limit,
        "offset": offset,
    }


@router.get("/stored/{mapping_id}")
async def get_stored_mapping(mapping_id: str):
    """Get a specific stored mapping by ID."""
    from mapping.persistence import get_mapping_store

    store = get_mapping_store(DB_PATH)
    mapping = store.get_mapping_by_id(mapping_id)

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    return mapping.to_dict()


@router.get("/stored/schema/{source_schema_id}")
async def get_mapping_by_schema(
    source_schema_id: str,
    version: int | None = None,
):
    """Get mapping for a source schema (latest version by default)."""
    from mapping.persistence import get_mapping_store

    store = get_mapping_store(DB_PATH)
    mapping = store.get_mapping(source_schema_id, version=version)

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    return mapping.to_dict()


@router.post("/stored/{mapping_id}/approve")
async def approve_stored_mapping(mapping_id: str, request: ApproveMappingRequest):
    """Approve a pending mapping."""
    from mapping.persistence import get_mapping_store

    store = get_mapping_store(DB_PATH)
    mapping = store.approve_mapping(mapping_id, approved_by=request.approved_by)

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    return {
        "mapping_id": mapping.id,
        "status": mapping.status.value,
        "approved_by": mapping.approved_by,
        "approved_at": mapping.approved_at,
    }


@router.post("/stored/{mapping_id}/reject")
async def reject_stored_mapping(mapping_id: str, request: RejectMappingRequest):
    """Reject a pending mapping."""
    from mapping.persistence import get_mapping_store

    store = get_mapping_store(DB_PATH)
    mapping = store.reject_mapping(
        mapping_id,
        rejected_by=request.rejected_by,
        reason=request.reason,
    )

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    return {
        "mapping_id": mapping.id,
        "status": mapping.status.value,
    }


@router.get("/stored/{mapping_id}/audit")
async def get_mapping_audit_log(
    mapping_id: str, limit: int = Query(default=50, ge=1, le=200)
):
    """Get audit log for a mapping."""
    from mapping.persistence import get_mapping_store

    store = get_mapping_store(DB_PATH)
    logs = store.get_audit_log(mapping_id, limit=limit)

    return {
        "mapping_id": mapping_id,
        "audit_log": [log.to_dict() for log in logs],
    }
