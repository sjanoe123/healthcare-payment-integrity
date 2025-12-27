"""Shared Pydantic schemas for the Healthcare Payment Integrity backend.

This module centralizes request/response models used across multiple routers
to prevent drift between duplicate definitions.
"""

from .mappings import SemanticMatchRequest

__all__ = ["SemanticMatchRequest"]
