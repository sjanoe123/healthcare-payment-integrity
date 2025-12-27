"""Policy search and document management routes.

This router handles RAG-powered policy document search and management,
including upload, filtering, and deletion of policy documents.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, model_validator

from rag import get_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["policies"])


# Pydantic models for request/response
class SearchQuery(BaseModel):
    """Query model for policy search with optional filters."""

    query: str
    n_results: int = 5
    top_k: int | None = None  # Accept frontend's top_k parameter
    sources: list[str] | None = None  # Filter by source(s)
    document_types: list[str] | None = None  # Filter by document type(s)
    effective_date: str | None = None  # Filter for policies effective at this date

    @model_validator(mode="after")
    def normalize_result_count(self) -> "SearchQuery":
        """Use top_k if n_results not explicitly set."""
        if self.top_k and self.n_results == 5:  # default was used
            object.__setattr__(self, "n_results", self.top_k)
        return self


class PolicyUploadRequest(BaseModel):
    """Request model for uploading policy documents."""

    content: str
    source: str = "user_upload"
    document_type: str = "policy"
    effective_date: str | None = None


def sanitize_filename(filename: str | None, max_length: int = 255) -> str:
    """Sanitize a user-provided filename for safe logging and storage."""
    if not filename:
        return "unknown"

    safe_name = filename.replace("\\", "/")
    safe_name = safe_name.split("/")[-1]
    safe_name = safe_name.replace("..", "")
    safe_name = re.sub(r"[\x00-\x1f\x7f-\x9f\n\r]", "", safe_name)

    if len(safe_name) > max_length:
        if "." in safe_name:
            name, ext = safe_name.rsplit(".", 1)
            ext = ext[:10]
            safe_name = name[: max_length - len(ext) - 1] + "." + ext
        else:
            safe_name = safe_name[:max_length]

    return safe_name or "unknown"


# Routes
@router.post("/search")
async def search_policies(query: SearchQuery):
    """Search policy documents using RAG with optional filters.

    Supports filtering by:
    - sources: List of source names (e.g., ["NCCI", "LCD"])
    - document_types: List of document types (e.g., ["policy", "guideline"])
    - effective_date: ISO date string to filter for currently effective policies
    """
    store = get_store()

    if store.count() == 0:
        return {
            "query": query.query,
            "results": [],
            "total_documents": 0,
            "filters_applied": {
                "sources": query.sources,
                "document_types": query.document_types,
                "effective_date": query.effective_date,
            },
            "message": "No documents indexed. Run seed_chromadb.py to add policy documents.",
        }

    # Build filters based on query parameters
    filters: dict[str, Any] | None = None

    if query.sources or query.document_types:
        filter_conditions = []
        if query.sources:
            if len(query.sources) == 1:
                filter_conditions.append({"source": query.sources[0]})
            else:
                filter_conditions.append({"source": {"$in": query.sources}})
        if query.document_types:
            if len(query.document_types) == 1:
                filter_conditions.append({"document_type": query.document_types[0]})
            else:
                filter_conditions.append(
                    {"document_type": {"$in": query.document_types}}
                )

        if len(filter_conditions) == 1:
            filters = filter_conditions[0]
        else:
            filters = {"$and": filter_conditions}

    # Use date-aware search if effective_date specified
    if query.effective_date:
        results = store.search_current_policies(
            query.query, query.effective_date, n_results=query.n_results
        )
    else:
        results = store.search(query.query, n_results=query.n_results, filters=filters)

    return {
        "query": query.query,
        "results": results,
        "total_documents": store.count(),
        "filters_applied": {
            "sources": query.sources,
            "document_types": query.document_types,
            "effective_date": query.effective_date,
        },
    }


@router.post("/policies/upload")
async def upload_policy_document(request: PolicyUploadRequest):
    """Upload a policy document to the RAG system.

    Accepts text content and adds it to the ChromaDB vector store
    for use in policy search and rules context.
    """
    store = get_store()

    if not request.content or len(request.content.strip()) < 10:
        raise HTTPException(
            status_code=400, detail="Document content must be at least 10 characters"
        )

    # Generate document ID
    doc_hash = hashlib.sha256(request.content.encode()).hexdigest()[:12]
    doc_id = f"upload_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{doc_hash}"

    # Build metadata
    metadata = {
        "source": request.source,
        "document_type": request.document_type,
        "upload_date": datetime.now(timezone.utc).isoformat(),
    }
    if request.effective_date:
        metadata["effective_date"] = request.effective_date

    store.add_documents(
        documents=[request.content],
        metadatas=[metadata],
        ids=[doc_id],
    )

    return {
        "success": True,
        "document_id": doc_id,
        "message": "Document uploaded successfully",
        "total_documents": store.count(),
    }


@router.post("/policies/upload-file")
async def upload_policy_file(
    file: UploadFile = File(...),
    source: str = Query(default="file_upload"),
    document_type: str = Query(default="policy"),
):
    """Upload a policy document file to the RAG system.

    Supports: .txt, .md files
    PDF support requires additional dependencies.
    """
    store = get_store()

    # Sanitize filename to prevent path traversal and log injection
    raw_filename = file.filename or "unknown"
    filename = sanitize_filename(raw_filename)

    # Check file extension
    allowed_extensions = {".txt", ".md"}
    file_ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )

    try:
        # Read file content
        content = await file.read()
        text_content = content.decode("utf-8")

        if len(text_content.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Document content must be at least 10 characters",
            )

        # Generate document ID
        doc_hash = hashlib.sha256(content).hexdigest()[:12]
        doc_id = (
            f"file_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{doc_hash}"
        )

        # Build metadata
        metadata = {
            "source": source,
            "document_type": document_type,
            "filename": filename,
            "upload_date": datetime.now(timezone.utc).isoformat(),
        }

        store.add_documents(
            documents=[text_content],
            metadatas=[metadata],
            ids=[doc_id],
        )

        return {
            "success": True,
            "document_id": doc_id,
            "filename": filename,
            "message": "File uploaded successfully",
            "total_documents": store.count(),
        }

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be valid UTF-8 text",
        )


@router.get("/policies/sources")
async def list_policy_sources():
    """List all unique policy sources and their document counts.

    Returns dictionary mapping source names to document counts.
    Useful for building filter UIs.
    """
    store = get_store()
    return {
        "sources": store.list_sources(),
        "total_documents": store.count(),
    }


@router.get("/policies/types")
async def list_policy_types():
    """List all unique document types and their counts.

    Returns dictionary mapping document types to counts.
    Useful for building filter UIs.
    """
    store = get_store()
    return {
        "document_types": store.list_document_types(),
        "total_documents": store.count(),
    }


@router.get("/policies/{document_id}")
async def get_policy_document(document_id: str):
    """Get a specific policy document by ID.

    Returns the document content and metadata.
    """
    store = get_store()
    document = store.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


@router.delete("/policies/{document_id}")
async def delete_policy_document(document_id: str):
    """Delete a policy document by ID.

    Returns success status.
    """
    store = get_store()
    deleted = store.delete_document(document_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "success": True,
        "document_id": document_id,
        "message": "Document deleted successfully",
        "total_documents": store.count(),
    }


@router.delete("/policies/source/{source_name}")
async def delete_policies_by_source(source_name: str):
    """Delete all policy documents from a specific source.

    Useful for bulk cleanup when re-importing updated policies.
    """
    # Validate source_name to prevent unexpected behavior
    if not source_name or not source_name.strip():
        raise HTTPException(status_code=400, detail="Source name cannot be empty")
    if len(source_name) > 256:
        raise HTTPException(
            status_code=400, detail="Source name too long (max 256 characters)"
        )

    store = get_store()
    count = store.bulk_delete_by_source(source_name)

    return {
        "success": True,
        "source": source_name,
        "deleted_count": count,
        "message": f"Deleted {count} documents from source '{source_name}'",
        "total_documents": store.count(),
    }
