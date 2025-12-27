"""API route modules for the Healthcare Payment Integrity platform.

This package contains focused routers that are registered with the main FastAPI app.
Each router handles a specific domain of functionality.

Routers:
- policies: RAG-powered policy search and document management
- mappings: OMOP CDM field mapping and semantic matching
- rules: Rule statistics and coverage analytics

TODO (Week 3+): Extract additional routers from app.py
- connectors: Data source connector management
- claims: Claim analysis and fraud detection
"""

from .mappings import router as mappings_router
from .policies import router as policies_router
from .rules import router as rules_router

__all__ = ["policies_router", "mappings_router", "rules_router"]
