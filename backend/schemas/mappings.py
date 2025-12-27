"""Pydantic schemas for field mapping endpoints."""

from pydantic import BaseModel, field_validator


class SemanticMatchRequest(BaseModel):
    """Request model for semantic field matching."""

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
