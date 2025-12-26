"""API route modules for the Healthcare Payment Integrity platform.

This package contains focused routers that are registered with the main FastAPI app.
Each router handles a specific domain of functionality.

Routers:
- policies: RAG-powered policy search and document management
- (future) claims: Claim analysis and fraud detection
- (future) connectors: Data source connector management
- (future) mappings: Field mapping configuration
"""

from .policies import router as policies_router

__all__ = ["policies_router"]
