"""Healthcare Payment Integrity Backend Package.

This package provides the FastAPI backend for the healthcare payment
integrity platform, including:

- Fraud detection rules engine
- RAG-powered policy search
- Data source connectors
- Field mapping and normalization
- Claude AI explanations via Kirk persona

Usage:
    # Development (from project root):
    PYTHONPATH=backend uvicorn app:app --reload --port 8080

    # Or using make:
    make run

    # Production:
    uvicorn backend.app:app --host 0.0.0.0 --port 8080

Modules:
    app: FastAPI application entry point
    rules: Fraud detection rules engine
    rag: ChromaDB vector store for policy retrieval
    mapping: OMOP CDM field normalization
    connectors: Database/file/API data source connectors
    scheduler: APScheduler background job management
    security: Credential encryption and management
    claude_client: Claude API integration
    kirk_config: Kirk AI persona configuration
"""

__version__ = "0.2.0"
