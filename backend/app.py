"""FastAPI backend for Healthcare Payment Integrity prototype."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rules import evaluate_baseline, ThresholdConfig
from rag import get_store
from claude_client import get_kirk_analysis
from kirk_config import KIRK_CONFIG
from mapping import normalize_claim
from mapping.templates import get_template

# Configure logging
logger = logging.getLogger(__name__)


# Database setup
DB_PATH = os.getenv("DB_PATH", "./data/prototype.db")

# Pagination limits
DEFAULT_JOBS_LIMIT = 100
MAX_JOBS_LIMIT = 1000


def safe_json_loads(
    data: str | None, default: list | dict | None = None
) -> list | dict:
    """Safely parse JSON, returning default on error."""
    if default is None:
        default = []
    if not data:
        return default
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON: {data[:100]}...")
        return default


def init_db():
    """Initialize SQLite database."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                claim_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                completed_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                job_id TEXT PRIMARY KEY,
                claim_id TEXT,
                fraud_score REAL,
                decision_mode TEXT,
                rule_hits TEXT,
                ncci_flags TEXT,
                coverage_flags TEXT,
                provider_flags TEXT,
                roi_estimate REAL,
                claude_explanation TEXT,
                created_at TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            )
        """)

        # Create indices for performance
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_results_created_at ON results(created_at DESC)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")

        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    init_db()
    # Pre-load ChromaDB
    get_store()
    yield


app = FastAPI(
    title="Healthcare Payment Integrity Prototype",
    description="Local fraud detection prototype with ChromaDB RAG",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "https://healthcare-payment-integrity.vercel.app",
    "https://healthcare-payment-integrity-*.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"https://healthcare-payment-integrity-[a-z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class ClaimItem(BaseModel):
    procedure_code: str
    diagnosis_code: str | None = None
    quantity: int = 1
    line_amount: float = 0.0
    modifier: str | None = None


class ClaimSubmission(BaseModel):
    claim_id: str
    billed_amount: float | None = None
    diagnosis_codes: list[str] = []
    items: list[ClaimItem]
    provider: dict[str, Any] | None = None
    member: dict[str, Any] | None = None


class AnalysisResult(BaseModel):
    job_id: str
    claim_id: str
    fraud_score: float
    decision_mode: str
    rule_hits: list[dict[str, Any]]
    ncci_flags: list[str]
    coverage_flags: list[str]
    provider_flags: list[str]
    roi_estimate: float | None
    claude_analysis: dict[str, Any]


class SearchQuery(BaseModel):
    query: str
    n_results: int = 5


# Sample reference datasets (load from files in production)
SAMPLE_DATASETS = {
    "ncci_ptp": {
        ("99213", "99214"): {"citation": "NCCI PTP Edit", "modifier": "25"},
        ("99214", "99215"): {"citation": "NCCI PTP Edit", "modifier": "25"},
        ("43239", "43235"): {"citation": "NCCI PTP Edit - Endoscopy", "modifier": None},
    },
    "ncci_mue": {
        "99213": {"limit": 1},
        "99214": {"limit": 1},
        "99215": {"limit": 1},
        "90834": {"limit": 4},
        "90837": {"limit": 4},
    },
    "lcd": {
        "99213": {
            "diagnosis_codes": {"J06.9", "J20.9", "R05.9", "J00"},
            "age_ranges": [{"min": 0, "max": 120}],
            "experimental": False,
        },
        "99214": {
            "diagnosis_codes": {"J06.9", "J20.9", "R05.9", "J00", "M54.5"},
            "age_ranges": [{"min": 0, "max": 120}],
            "experimental": False,
        },
    },
    "oig_exclusions": {"1234567890"},  # Sample excluded NPI
    "fwa_watchlist": {"9876543210"},  # Sample watched NPI
    "mpfs": {
        "99213": {"regions": {"national": 95.0}, "global_surgery": None},
        "99214": {"regions": {"national": 130.0}, "global_surgery": None},
        "99215": {"regions": {"national": 175.0}, "global_surgery": None},
    },
    "utilization": {},
    "fwa_config": {
        "roi_multiplier": 1.0,
        "volume_threshold": 3,
        "high_risk_specialties": ["pain management", "durable medical equipment"],
        "geographic_distance_km": 100,
    },
}


def load_datasets() -> dict[str, Any]:
    """Load reference datasets from files or return samples."""
    data_dir = Path("./data")

    datasets = SAMPLE_DATASETS.copy()

    # Try to load from JSON files if they exist
    for dataset_name in ["ncci_mue", "lcd", "mpfs", "fwa_config"]:
        json_path = data_dir / f"{dataset_name}.json"
        if json_path.exists():
            with open(json_path) as f:
                datasets[dataset_name] = json.load(f)

    # Load NCCI PTP (convert list format to dict with tuple keys)
    ncci_ptp_path = data_dir / "ncci_ptp.json"
    if ncci_ptp_path.exists():
        with open(ncci_ptp_path) as f:
            ptp_list = json.load(f)
            ptp_dict = {}
            for entry in ptp_list:
                codes = entry.get("codes", [])
                if len(codes) == 2:
                    key = tuple(sorted(codes))
                    ptp_dict[key] = {
                        "citation": entry.get("citation"),
                        "modifier": entry.get("modifier"),
                    }
            datasets["ncci_ptp"] = ptp_dict
            print(f"Loaded {len(ptp_dict):,} NCCI PTP code pairs")

    # Load OIG exclusions (special format with excluded_npis list)
    oig_path = data_dir / "oig_exclusions.json"
    if oig_path.exists():
        with open(oig_path) as f:
            oig_data = json.load(f)
            # Convert list to set for fast lookups
            datasets["oig_exclusions"] = set(oig_data.get("excluded_npis", []))
            print(f"Loaded {len(datasets['oig_exclusions']):,} OIG excluded NPIs")

    return datasets


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "rag_documents": get_store().count(),
    }


@app.post("/api/upload", response_model=dict)
async def upload_claim(claim: ClaimSubmission):
    """Submit a claim for analysis."""
    job_id = str(uuid.uuid4())

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO jobs (job_id, claim_id, status, created_at) VALUES (?, ?, ?, ?)",
            (job_id, claim.claim_id, "pending", datetime.utcnow().isoformat()),
        )
        conn.commit()

    return {
        "job_id": job_id,
        "claim_id": claim.claim_id,
        "status": "pending",
        "message": "Claim submitted. Call /api/analyze/{job_id} to process.",
    }


@app.post("/api/analyze/{job_id}")
async def analyze_claim(
    job_id: str,
    claim: ClaimSubmission,
    mapping_template: str | None = Query(
        default=None,
        description="Mapping template to use: 'edi_837p', 'edi_837i', or 'csv'",
    ),
):
    """Run fraud analysis on a claim.

    Args:
        job_id: Unique job identifier from /api/upload
        claim: Claim data to analyze
        mapping_template: Optional pre-built mapping template name.
            Available templates: 'edi_837p', 'edi_837i', 'csv'.
            If not specified, alias-based mapping is used.
    """

    # Load reference datasets
    datasets = load_datasets()

    # Convert claim to dict for rules engine
    raw_claim = {
        "claim_id": claim.claim_id,
        "billed_amount": claim.billed_amount or sum(i.line_amount for i in claim.items),
        "diagnosis_codes": claim.diagnosis_codes,
        "items": [item.model_dump() for item in claim.items],
        "provider": claim.provider or {},
        "member": claim.member or {},
    }

    # Normalize claim to OMOP CDM canonical schema
    custom_mapping = None
    if mapping_template:
        try:
            custom_mapping = get_template(mapping_template)
            logger.info(f"Using mapping template: {mapping_template}")
        except ValueError as e:
            logger.warning(f"Invalid mapping template: {e}")

    claim_dict = normalize_claim(raw_claim, custom_mapping=custom_mapping)

    # Run rules engine
    outcome = evaluate_baseline(
        claim=claim_dict,
        datasets=datasets,
        config={"base_score": 0.5},
        threshold_config=ThresholdConfig(),
    )

    # Get RAG context if available
    rag_context = None
    store = get_store()
    if store.count() > 0:
        # Search for relevant policy context
        search_query = (
            f"Procedure codes: {', '.join(i.procedure_code for i in claim.items)}"
        )
        rag_results = store.search(search_query, n_results=3)
        if rag_results:
            rag_context = "\n\n".join(
                f"[{r['metadata'].get('source', 'Policy')}]: {r['content'][:500]}..."
                for r in rag_results
            )

    # Get Kirk's expert analysis
    claude_result = get_kirk_analysis(
        claim=claim_dict,
        rule_hits=outcome.rule_result.hits,
        fraud_score=outcome.decision.score,
        decision_mode=outcome.decision.decision_mode,
        rag_context=rag_context,
        config=KIRK_CONFIG,
    )

    # Store results
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """INSERT OR REPLACE INTO results
               (job_id, claim_id, fraud_score, decision_mode, rule_hits,
                ncci_flags, coverage_flags, provider_flags, roi_estimate,
                claude_explanation, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                claim.claim_id,
                outcome.decision.score,
                outcome.decision.decision_mode,
                json.dumps([asdict(h) for h in outcome.rule_result.hits]),
                json.dumps(outcome.ncci_flags),
                json.dumps(outcome.coverage_flags),
                json.dumps(outcome.provider_flags),
                outcome.roi_estimate,
                json.dumps(claude_result),
                datetime.utcnow().isoformat(),
            ),
        )

        cursor.execute(
            "UPDATE jobs SET status = ?, completed_at = ? WHERE job_id = ?",
            ("completed", datetime.utcnow().isoformat(), job_id),
        )

        conn.commit()

    return AnalysisResult(
        job_id=job_id,
        claim_id=claim.claim_id,
        fraud_score=outcome.decision.score,
        decision_mode=outcome.decision.decision_mode,
        rule_hits=[asdict(h) for h in outcome.rule_result.hits],
        ncci_flags=outcome.ncci_flags,
        coverage_flags=outcome.coverage_flags,
        provider_flags=outcome.provider_flags,
        roi_estimate=outcome.roi_estimate,
        claude_analysis=claude_result,
    )


@app.get("/api/results/{job_id}")
async def get_results(job_id: str):
    """Get analysis results for a job."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM results WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=404, detail=f"Results not found for job {job_id}"
        )

    return {
        "job_id": row[0],
        "claim_id": row[1],
        "fraud_score": row[2],
        "decision_mode": row[3],
        "rule_hits": json.loads(row[4]) if row[4] else [],
        "ncci_flags": json.loads(row[5]) if row[5] else [],
        "coverage_flags": json.loads(row[6]) if row[6] else [],
        "provider_flags": json.loads(row[7]) if row[7] else [],
        "roi_estimate": row[8],
        "claude_analysis": json.loads(row[9]) if row[9] else {},
        "created_at": row[10],
    }


@app.post("/api/search")
async def search_policies(query: SearchQuery):
    """Search policy documents using RAG."""
    store = get_store()

    if store.count() == 0:
        return {
            "results": [],
            "message": "No documents indexed. Run seed_chromadb.py to add policy documents.",
        }

    results = store.search(query.query, n_results=query.n_results)

    return {
        "query": query.query,
        "results": results,
        "total_documents": store.count(),
    }


@app.get("/api/mappings/templates")
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


class MappingPreviewRequest(BaseModel):
    sample_data: dict[str, Any]
    template: str | None = None


@app.post("/api/mappings/preview")
async def preview_mapping(request: MappingPreviewRequest):
    """Preview how sample data would be mapped to OMOP CDM schema.

    This endpoint allows testing field mappings before submitting claims.
    """
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


@app.get("/api/mappings/schema")
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


class SemanticMatchRequest(BaseModel):
    source_fields: list[str]
    top_k: int = 5
    min_similarity: float = 0.3


@app.post("/api/mappings/semantic")
async def find_semantic_matches(request: SemanticMatchRequest):
    """Find semantic matches for unknown field names using PubMedBERT embeddings.

    This endpoint uses biomedical embeddings to find the closest OMOP CDM
    field matches for unknown field names. Useful for mapping fields from
    new data sources that don't match built-in aliases.
    """
    try:
        from mapping.embeddings import get_embedding_matcher
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Semantic matching unavailable: sentence-transformers not installed",
        )

    matcher = get_embedding_matcher()

    if len(request.source_fields) == 1:
        # Single field
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
        # Batch mode
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


class SemanticPreviewRequest(BaseModel):
    sample_data: dict[str, Any]
    template: str | None = None
    use_semantic: bool = True
    semantic_threshold: float = 0.7


class RerankerRequest(BaseModel):
    """Request model for LLM reranking."""

    source_field: str
    candidates: list[dict[str, Any]]  # [{"field": "person_id", "score": 0.85}, ...]
    sample_values: list[Any] | None = None


class BatchRerankerRequest(BaseModel):
    """Request model for batch LLM reranking."""

    mappings: list[dict[str, Any]]


@app.post("/api/mappings/preview/semantic")
async def preview_semantic_mapping(request: SemanticPreviewRequest):
    """Preview field mapping with semantic matching for unknown fields.

    This endpoint shows how semantic matching would handle fields that
    don't match built-in aliases. Returns both the normalized claim and
    details about which fields were matched semantically.
    """
    from mapping import normalize_claim_with_review

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
            source
            for source, (_, score) in semantic_matches.items()
            if score < 0.85  # Flag lower confidence matches
        ],
    }


@app.post("/api/mappings/rerank")
async def rerank_field_mapping(request: RerankerRequest):
    """Rerank semantic mapping candidates using Claude Haiku 4.5.

    This endpoint takes embedding candidates and uses LLM intelligence to
    select the best match with a confidence score and reasoning. Use this
    for human-in-the-loop workflows where semantic matches need validation.
    """
    from mapping.reranker import rerank_mapping

    # Convert candidates from API format to internal format
    candidates = [
        (
            c.get("field") or c.get("canonical_field"),
            c.get("score") or c.get("similarity", 0.0),
        )
        for c in request.candidates
    ]

    result = rerank_mapping(
        source_field=request.source_field,
        candidates=candidates,
        sample_values=request.sample_values,
    )

    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Reranking failed - check ANTHROPIC_API_KEY is set",
        )

    return result.to_dict()


@app.post("/api/mappings/rerank/batch")
async def batch_rerank_mappings(request: BatchRerankerRequest):
    """Batch rerank multiple field mappings.

    Process multiple field mappings in a single request. Each mapping
    needs a source_field, candidates list, and optional sample_values.
    """
    from mapping.reranker import get_reranker

    reranker = get_reranker()

    # Convert all mappings to internal format
    internal_mappings = []
    for mapping in request.mappings:
        candidates = [
            (
                c.get("field") or c.get("canonical_field"),
                c.get("score") or c.get("similarity", 0.0),
            )
            for c in mapping.get("candidates", [])
        ]
        internal_mappings.append(
            {
                "source_field": mapping["source_field"],
                "candidates": candidates,
                "sample_values": mapping.get("sample_values"),
            }
        )

    results = reranker.batch_rerank(internal_mappings)

    return {
        "results": [r.to_dict() if r else None for r in results],
        "success_count": sum(1 for r in results if r is not None),
        "failed_count": sum(1 for r in results if r is None),
        "needs_review": [
            r.to_dict() for r in results if r is not None and r.needs_review()
        ],
    }


@app.post("/api/mappings/smart")
async def smart_field_mapping(request: SemanticMatchRequest):
    """Smart field mapping: Embedding + LLM reranking pipeline.

    This endpoint combines PubMedBERT embeddings with Claude Haiku reranking
    for high-confidence field mapping. Use this for automated mapping with
    confidence scoring.
    """
    try:
        from mapping.embeddings import get_embedding_matcher
        from mapping.reranker import get_reranker
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Smart mapping unavailable: {e}",
        )

    matcher = get_embedding_matcher()
    reranker = get_reranker()

    results = []
    for source_field in request.source_fields:
        # Step 1: Get embedding candidates
        candidates = matcher.find_candidates(
            source_field,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )

        if not candidates:
            results.append(
                {
                    "source_field": source_field,
                    "status": "no_candidates",
                    "best_match": None,
                }
            )
            continue

        # Step 2: Rerank with LLM
        reranked = reranker.rerank(source_field, candidates)

        if reranked:
            results.append(
                {
                    "source_field": source_field,
                    "status": "success",
                    "best_match": reranked.to_dict(),
                    "embedding_candidates": [
                        {"field": f, "score": round(s, 4)} for f, s in candidates
                    ],
                }
            )
        else:
            # Fallback to embedding best match
            results.append(
                {
                    "source_field": source_field,
                    "status": "rerank_failed",
                    "best_match": {
                        "target_field": candidates[0][0],
                        "confidence": int(candidates[0][1] * 100),
                        "reasoning": "LLM reranking unavailable, using embedding similarity",
                        "needs_review": True,
                    },
                    "embedding_candidates": [
                        {"field": f, "score": round(s, 4)} for f, s in candidates
                    ],
                }
            )

    return {
        "results": results,
        "high_confidence": [
            r for r in results if r.get("best_match", {}).get("confidence", 0) >= 85
        ],
        "needs_review": [
            r for r in results if r.get("best_match", {}).get("needs_review", True)
        ],
    }


# ============================================================================
# Mapping Persistence Endpoints
# ============================================================================


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


@app.post("/api/mappings/save")
async def save_mapping(request: SaveMappingRequest):
    """Save a new schema mapping for review.

    Creates a new mapping version and stores it with audit trail.
    The mapping starts in 'pending' status until approved.
    """
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


@app.get("/api/mappings/stored")
async def list_stored_mappings(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List stored schema mappings with optional status filter."""
    from mapping.persistence import get_mapping_store, MappingStatus

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


@app.get("/api/mappings/stored/{mapping_id}")
async def get_stored_mapping(mapping_id: str):
    """Get a specific stored mapping by ID."""
    from mapping.persistence import get_mapping_store

    store = get_mapping_store(DB_PATH)
    mapping = store.get_mapping_by_id(mapping_id)

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    return mapping.to_dict()


@app.get("/api/mappings/stored/schema/{source_schema_id}")
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


@app.post("/api/mappings/stored/{mapping_id}/approve")
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


@app.post("/api/mappings/stored/{mapping_id}/reject")
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


@app.get("/api/mappings/stored/{mapping_id}/audit")
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


@app.get("/api/jobs")
async def list_jobs(
    limit: int = Query(default=DEFAULT_JOBS_LIMIT, ge=1, le=MAX_JOBS_LIMIT),
    offset: int = Query(default=0, ge=0),
):
    """List analyzed claims with pagination."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.job_id, r.claim_id, r.fraud_score, r.decision_mode,
                   r.rule_hits, r.ncci_flags, r.coverage_flags, r.provider_flags,
                   r.roi_estimate, r.created_at, j.status
            FROM results r
            JOIN jobs j ON r.job_id = j.job_id
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )
        rows = cursor.fetchall()

    jobs = []
    for row in rows:
        rule_hits = safe_json_loads(row[4])
        ncci_flags = safe_json_loads(row[5])
        coverage_flags = safe_json_loads(row[6])
        provider_flags = safe_json_loads(row[7])

        jobs.append(
            {
                "job_id": row[0],
                "claim_id": row[1],
                "fraud_score": row[2],
                "decision_mode": row[3],
                "rule_hits": rule_hits,
                "ncci_flags": ncci_flags,
                "coverage_flags": coverage_flags,
                "provider_flags": provider_flags,
                "roi_estimate": row[8],
                "created_at": row[9],
                "status": row[10],
                "flags_count": len(rule_hits)
                + len(ncci_flags)
                + len(coverage_flags)
                + len(provider_flags),
            }
        )

    return {"jobs": jobs, "total": len(jobs), "limit": limit, "offset": offset}


@app.get("/api/stats")
async def get_stats():
    """Get prototype statistics."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM jobs")
        total_jobs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'completed'")
        completed_jobs = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(fraud_score) FROM results")
        avg_score = cursor.fetchone()[0] or 0

        # Count flags
        cursor.execute(
            "SELECT rule_hits, ncci_flags, coverage_flags, provider_flags FROM results"
        )
        rows = cursor.fetchall()
        total_flags = 0
        auto_approved = 0
        for row in rows:
            rule_hits = safe_json_loads(row[0])
            ncci_flags = safe_json_loads(row[1])
            coverage_flags = safe_json_loads(row[2])
            provider_flags = safe_json_loads(row[3])
            flags = (
                len(rule_hits)
                + len(ncci_flags)
                + len(coverage_flags)
                + len(provider_flags)
            )
            total_flags += flags
            if flags == 0:
                auto_approved += 1

        cursor.execute(
            "SELECT SUM(roi_estimate) FROM results WHERE roi_estimate IS NOT NULL"
        )
        total_roi = cursor.fetchone()[0] or 0

    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "avg_fraud_score": round(avg_score, 3),
        "rag_documents": get_store().count(),
        # Frontend expected fields
        "claims_analyzed": completed_jobs,
        "flags_detected": total_flags,
        "auto_approved": auto_approved,
        "potential_savings": round(total_roi, 2),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
