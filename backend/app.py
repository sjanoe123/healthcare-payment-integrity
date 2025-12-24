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

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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

        # ============================================================
        # Data Source Connector Tables
        # ============================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connectors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                connector_type TEXT NOT NULL,
                subtype TEXT NOT NULL,
                data_type TEXT NOT NULL,
                connection_config TEXT NOT NULL,
                sync_schedule TEXT,
                sync_mode TEXT DEFAULT 'incremental',
                batch_size INTEGER DEFAULT 1000,
                field_mapping_id TEXT,
                status TEXT DEFAULT 'inactive',
                last_sync_at TEXT,
                last_sync_status TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_jobs (
                id TEXT PRIMARY KEY,
                connector_id TEXT NOT NULL,
                job_type TEXT NOT NULL,
                sync_mode TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                started_at TEXT,
                completed_at TEXT,
                total_records INTEGER DEFAULT 0,
                processed_records INTEGER DEFAULT 0,
                failed_records INTEGER DEFAULT 0,
                watermark_value TEXT,
                error_message TEXT,
                triggered_by TEXT,
                FOREIGN KEY (connector_id) REFERENCES connectors(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_job_logs (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                context TEXT,
                FOREIGN KEY (job_id) REFERENCES sync_jobs(id)
            )
        """)

        # Connector indices
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_connectors_type ON connectors(connector_type)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_connectors_status ON connectors(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sync_jobs_connector ON sync_jobs(connector_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sync_job_logs_job ON sync_job_logs(job_id)"
        )

        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    init_db()
    # Pre-load ChromaDB
    get_store()

    # Pre-load embedding model if configured (reduces first-request latency)
    if os.getenv("PRELOAD_EMBEDDINGS", "false").lower() == "true":
        try:
            from mapping.embeddings import get_embedding_matcher

            logger.info("Pre-loading embedding model...")
            get_embedding_matcher()
            logger.info("Embedding model loaded successfully")
        except ImportError:
            logger.warning(
                "Embedding model preload skipped: sentence-transformers not installed"
            )
        except Exception as e:
            logger.warning(f"Embedding model preload failed: {e}")

    # Initialize scheduler for background sync jobs
    scheduler = None
    try:
        from scheduler import start_scheduler, shutdown_scheduler

        scheduler = start_scheduler(DB_PATH)
        logger.info("Scheduler started for background sync jobs")
    except ImportError:
        logger.warning("Scheduler not available: APScheduler not installed")
    except Exception as e:
        logger.warning(f"Scheduler initialization failed: {e}")

    yield

    # Cleanup scheduler on shutdown
    if scheduler:
        try:
            shutdown_scheduler(wait=True)
            logger.info("Scheduler shutdown complete")
        except Exception as e:
            logger.warning(f"Scheduler shutdown error: {e}")


app = FastAPI(
    title="Healthcare Payment Integrity Prototype",
    description="Local fraud detection prototype with ChromaDB RAG",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting configuration
# LLM endpoints: 10 requests/minute (costly API calls)
# Standard endpoints: 100 requests/minute
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

    @field_validator("source_fields")
    @classmethod
    def validate_source_fields_length(cls, v: list[str]) -> list[str]:
        """Validate that source_fields doesn't exceed maximum length."""
        if len(v) > 100:
            raise ValueError("Too many fields. Maximum 100 per request.")
        return v


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

    @field_validator("mappings")
    @classmethod
    def validate_batch_size(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate batch size to prevent excessive LLM API calls."""
        if len(v) > 20:
            raise ValueError("Batch size too large. Maximum 20 mappings per request.")
        return v


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
@limiter.limit("10/minute")
async def rerank_field_mapping(request: Request, rerank_request: RerankerRequest):
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
        for c in rerank_request.candidates
    ]

    result = rerank_mapping(
        source_field=rerank_request.source_field,
        candidates=candidates,
        sample_values=rerank_request.sample_values,
    )

    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Reranking failed - check ANTHROPIC_API_KEY is set",
        )

    return result.to_dict()


@app.post("/api/mappings/rerank/batch")
@limiter.limit("5/minute")
async def batch_rerank_mappings(request: Request, batch_request: BatchRerankerRequest):
    """Batch rerank multiple field mappings.

    Process multiple field mappings in a single request. Each mapping
    needs a source_field, candidates list, and optional sample_values.
    Rate limited to 5 requests/minute due to multiple LLM calls per request.
    """
    from mapping.reranker import get_reranker

    reranker = get_reranker()

    # Convert all mappings to internal format
    internal_mappings = []
    for mapping in batch_request.mappings:
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
@limiter.limit("10/minute")
async def smart_field_mapping(request: Request, smart_request: SemanticMatchRequest):
    """Smart field mapping: Embedding + LLM reranking pipeline.

    This endpoint combines PubMedBERT embeddings with Claude Haiku reranking
    for high-confidence field mapping. Use this for automated mapping with
    confidence scoring. Rate limited to 10 requests/minute.
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
    for source_field in smart_request.source_fields:
        # Step 1: Get embedding candidates
        candidates = matcher.find_candidates(
            source_field,
            top_k=smart_request.top_k,
            min_similarity=smart_request.min_similarity,
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


# ============================================================================
# Data Source Connector Endpoints
# ============================================================================

# Secret fields that need encryption for each connector type
CONNECTOR_SECRET_FIELDS = {
    "database": ["password"],
    "api": ["api_key", "oauth_client_secret"],
    "file": ["aws_access_key", "aws_secret_key", "password", "private_key"],
}


@app.get("/api/connectors/types")
async def list_connector_types():
    """List available connector types and their configuration schemas."""
    return {
        "types": [
            {
                "type": "database",
                "subtypes": [
                    {
                        "subtype": "postgresql",
                        "name": "PostgreSQL",
                        "description": "Connect to PostgreSQL databases",
                    },
                    {
                        "subtype": "mysql",
                        "name": "MySQL",
                        "description": "Connect to MySQL databases",
                    },
                    {
                        "subtype": "sqlserver",
                        "name": "SQL Server",
                        "description": "Connect to Microsoft SQL Server",
                    },
                ],
            },
            {
                "type": "api",
                "subtypes": [
                    {
                        "subtype": "rest",
                        "name": "REST API",
                        "description": "Connect to REST APIs",
                    },
                    {
                        "subtype": "fhir",
                        "name": "HL7 FHIR",
                        "description": "Connect to FHIR R4 servers",
                    },
                ],
            },
            {
                "type": "file",
                "subtypes": [
                    {
                        "subtype": "s3",
                        "name": "Amazon S3",
                        "description": "Read files from S3 buckets",
                    },
                    {
                        "subtype": "sftp",
                        "name": "SFTP",
                        "description": "Read files via SFTP",
                    },
                    {
                        "subtype": "azure_blob",
                        "name": "Azure Blob",
                        "description": "Read files from Azure Blob Storage",
                    },
                ],
            },
        ],
        "data_types": ["claims", "eligibility", "providers", "reference"],
    }


@app.get("/api/connectors")
async def list_connectors(
    connector_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List all configured connectors."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM connectors WHERE 1=1"
        params: list[Any] = []

        if connector_type:
            query += " AND connector_type = ?"
            params.append(connector_type)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

    connectors = []
    for row in rows:
        config = safe_json_loads(row["connection_config"], {})
        # Redact secrets in response
        for field in CONNECTOR_SECRET_FIELDS.get(row["connector_type"], []):
            if field in config:
                config[field] = "***"

        connectors.append(
            {
                "id": row["id"],
                "name": row["name"],
                "connector_type": row["connector_type"],
                "subtype": row["subtype"],
                "data_type": row["data_type"],
                "connection_config": config,
                "sync_schedule": row["sync_schedule"],
                "sync_mode": row["sync_mode"],
                "batch_size": row["batch_size"],
                "field_mapping_id": row["field_mapping_id"],
                "status": row["status"],
                "last_sync_at": row["last_sync_at"],
                "last_sync_status": row["last_sync_status"],
                "created_at": row["created_at"],
                "created_by": row["created_by"],
            }
        )

    return {
        "connectors": connectors,
        "total": len(connectors),
        "limit": limit,
        "offset": offset,
    }


class ConnectorCreateRequest(BaseModel):
    """Request model for creating a connector."""

    name: str
    connector_type: str
    subtype: str
    data_type: str
    connection_config: dict[str, Any]
    sync_schedule: str | None = None
    sync_mode: str = "incremental"
    batch_size: int = 1000
    field_mapping_id: str | None = None
    created_by: str | None = None


@app.post("/api/connectors")
async def create_connector(request: ConnectorCreateRequest):
    """Create a new data source connector."""
    from security import get_credential_manager

    connector_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Extract and encrypt secrets
    config = request.connection_config.copy()
    secret_fields = CONNECTOR_SECRET_FIELDS.get(request.connector_type, [])

    try:
        cred_manager = get_credential_manager(DB_PATH)
        if cred_manager.encryption_enabled:
            config = cred_manager.extract_and_store_secrets(
                connector_id, config, secret_fields
            )
    except Exception as e:
        logger.warning(f"Credential encryption failed: {e}")
        # Store without encryption (not recommended for production)
        for field in secret_fields:
            if field in config:
                config[field] = "***UNENCRYPTED***"

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO connectors
                    (id, name, connector_type, subtype, data_type, connection_config,
                     sync_schedule, sync_mode, batch_size, field_mapping_id, status,
                     created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    connector_id,
                    request.name,
                    request.connector_type,
                    request.subtype,
                    request.data_type,
                    json.dumps(config),
                    request.sync_schedule,
                    request.sync_mode,
                    request.batch_size,
                    request.field_mapping_id,
                    "inactive",
                    now,
                    request.created_by,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail=f"Connector with name '{request.name}' already exists",
            )

    return {
        "id": connector_id,
        "name": request.name,
        "connector_type": request.connector_type,
        "subtype": request.subtype,
        "status": "inactive",
        "created_at": now,
    }


@app.get("/api/connectors/{connector_id}")
async def get_connector(connector_id: str):
    """Get connector details by ID."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM connectors WHERE id = ?", (connector_id,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Connector not found")

    config = safe_json_loads(row["connection_config"], {})
    # Redact secrets
    for field in CONNECTOR_SECRET_FIELDS.get(row["connector_type"], []):
        if field in config:
            config[field] = "***"

    return {
        "id": row["id"],
        "name": row["name"],
        "connector_type": row["connector_type"],
        "subtype": row["subtype"],
        "data_type": row["data_type"],
        "connection_config": config,
        "sync_schedule": row["sync_schedule"],
        "sync_mode": row["sync_mode"],
        "batch_size": row["batch_size"],
        "field_mapping_id": row["field_mapping_id"],
        "status": row["status"],
        "last_sync_at": row["last_sync_at"],
        "last_sync_status": row["last_sync_status"],
        "created_at": row["created_at"],
        "created_by": row["created_by"],
    }


class ConnectorUpdateRequest(BaseModel):
    """Request model for updating a connector."""

    name: str | None = None
    connection_config: dict[str, Any] | None = None
    sync_schedule: str | None = None
    sync_mode: str | None = None
    batch_size: int | None = None
    field_mapping_id: str | None = None


@app.put("/api/connectors/{connector_id}")
async def update_connector(connector_id: str, request: ConnectorUpdateRequest):
    """Update a connector configuration."""
    from security import get_credential_manager

    # First fetch existing connector
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM connectors WHERE id = ?", (connector_id,))
        existing = cursor.fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Build update query
    updates = []
    params: list[Any] = []

    if request.name is not None:
        updates.append("name = ?")
        params.append(request.name)

    if request.connection_config is not None:
        config = request.connection_config.copy()
        secret_fields = CONNECTOR_SECRET_FIELDS.get(existing["connector_type"], [])

        try:
            cred_manager = get_credential_manager(DB_PATH)
            if cred_manager.encryption_enabled:
                config = cred_manager.extract_and_store_secrets(
                    connector_id, config, secret_fields
                )
        except Exception as e:
            logger.warning(f"Credential encryption failed: {e}")

        updates.append("connection_config = ?")
        params.append(json.dumps(config))

    if request.sync_schedule is not None:
        updates.append("sync_schedule = ?")
        params.append(request.sync_schedule)

    if request.sync_mode is not None:
        updates.append("sync_mode = ?")
        params.append(request.sync_mode)

    if request.batch_size is not None:
        updates.append("batch_size = ?")
        params.append(request.batch_size)

    if request.field_mapping_id is not None:
        updates.append("field_mapping_id = ?")
        params.append(request.field_mapping_id)

    if not updates:
        return {"message": "No changes provided"}

    params.append(connector_id)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE connectors SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()

    return {"message": "Connector updated", "connector_id": connector_id}


@app.delete("/api/connectors/{connector_id}")
async def delete_connector(connector_id: str):
    """Delete a connector and its credentials."""
    from security import get_credential_manager

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Check if connector exists
        cursor.execute("SELECT id FROM connectors WHERE id = ?", (connector_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Connector not found")

        # Delete credentials first
        try:
            cred_manager = get_credential_manager(DB_PATH)
            cred_manager.delete_credentials(connector_id)
        except Exception as e:
            logger.warning(f"Failed to delete credentials: {e}")

        # Delete sync jobs and logs
        cursor.execute(
            "DELETE FROM sync_job_logs WHERE job_id IN (SELECT id FROM sync_jobs WHERE connector_id = ?)",
            (connector_id,),
        )
        cursor.execute("DELETE FROM sync_jobs WHERE connector_id = ?", (connector_id,))

        # Delete connector
        cursor.execute("DELETE FROM connectors WHERE id = ?", (connector_id,))
        conn.commit()

    return {"message": "Connector deleted", "connector_id": connector_id}


@app.post("/api/connectors/{connector_id}/test")
async def test_connector(connector_id: str):
    """Test a connector's connection."""
    from security import get_credential_manager

    # Get connector details
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM connectors WHERE id = ?", (connector_id,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Connector not found")

    connector_type = row["connector_type"]
    subtype = row["subtype"]

    # Get connection config and inject secrets
    config = safe_json_loads(row["connection_config"], {})
    secret_fields = CONNECTOR_SECRET_FIELDS.get(connector_type, [])

    try:
        cred_manager = get_credential_manager(DB_PATH)
        config = cred_manager.inject_secrets(connector_id, config, secret_fields)
    except Exception as e:
        logger.warning(f"Failed to inject secrets: {e}")

    # Update status to testing
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE connectors SET status = ? WHERE id = ?",
            ("testing", connector_id),
        )
        conn.commit()

    # Test connection based on connector type
    if connector_type == "database":
        result = _test_database_connection(connector_id, subtype, config)
    elif connector_type == "api":
        result = _test_api_connection(connector_id, subtype, config)
    elif connector_type == "file":
        result = _test_file_connection(connector_id, subtype, config)
    else:
        result = {
            "success": False,
            "message": f"Unknown connector type: {connector_type}",
            "latency_ms": None,
            "details": {},
        }

    # Update connector status based on result
    new_status = "inactive" if result["success"] else "error"
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE connectors SET status = ? WHERE id = ?",
            (new_status, connector_id),
        )
        conn.commit()

    return result


def _test_database_connection(
    connector_id: str, subtype: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Test a database connection."""
    try:
        if subtype == "postgresql":
            from connectors.database import PostgreSQLConnector

            connector = PostgreSQLConnector(
                connector_id=connector_id,
                name="test",
                config=config,
            )
            result = connector.test_connection()
            return {
                "success": result.success,
                "message": result.message,
                "latency_ms": result.latency_ms,
                "details": result.details,
            }

        elif subtype == "mysql":
            from connectors.database import MySQLConnector

            connector = MySQLConnector(
                connector_id=connector_id,
                name="test",
                config=config,
            )
            result = connector.test_connection()
            return {
                "success": result.success,
                "message": result.message,
                "latency_ms": result.latency_ms,
                "details": result.details,
            }

        else:
            return {
                "success": False,
                "message": f"Database subtype '{subtype}' not yet implemented",
                "latency_ms": None,
                "details": {"subtype": subtype},
            }

    except ImportError as e:
        return {
            "success": False,
            "message": f"Missing dependency: {e}. Install with pip install sqlalchemy",
            "latency_ms": None,
            "details": {"error": str(e)},
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)[:200]}",
            "latency_ms": None,
            "details": {"error_type": type(e).__name__},
        }


def _test_api_connection(
    connector_id: str, subtype: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Test an API connection."""
    # API connectors will be implemented in Phase 5
    return {
        "success": True,
        "message": f"API connector '{subtype}' test pending implementation (Phase 5)",
        "latency_ms": None,
        "details": {"subtype": subtype, "base_url": config.get("base_url")},
    }


def _test_file_connection(
    connector_id: str, subtype: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Test a file system connection."""
    # File connectors will be implemented in Phase 4
    return {
        "success": True,
        "message": f"File connector '{subtype}' test pending implementation (Phase 4)",
        "latency_ms": None,
        "details": {"subtype": subtype},
    }


@app.get("/api/connectors/{connector_id}/schema")
async def discover_connector_schema(connector_id: str):
    """Discover schema from a database connector."""
    from security import get_credential_manager

    # Get connector details
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM connectors WHERE id = ?", (connector_id,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Connector not found")

    if row["connector_type"] != "database":
        raise HTTPException(
            status_code=400,
            detail="Schema discovery is only available for database connectors",
        )

    # Get connection config and inject secrets
    config = safe_json_loads(row["connection_config"], {})
    secret_fields = CONNECTOR_SECRET_FIELDS.get(row["connector_type"], [])

    try:
        cred_manager = get_credential_manager(DB_PATH)
        config = cred_manager.inject_secrets(connector_id, config, secret_fields)
    except Exception as e:
        logger.warning(f"Failed to inject secrets: {e}")

    subtype = row["subtype"]

    try:
        if subtype == "postgresql":
            from connectors.database import PostgreSQLConnector

            connector = PostgreSQLConnector(
                connector_id=connector_id,
                name=row["name"],
                config=config,
            )
        elif subtype == "mysql":
            from connectors.database import MySQLConnector

            connector = MySQLConnector(
                connector_id=connector_id,
                name=row["name"],
                config=config,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Schema discovery not supported for {subtype}",
            )

        # Discover schema
        with connector:
            result = connector.discover_schema()

        return {
            "connector_id": connector_id,
            "connector_name": row["name"],
            "tables": result.tables,
            "columns": result.columns,
            "sample_data": result.sample_data,
        }

    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Missing dependency: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Schema discovery failed: {str(e)[:200]}",
        )


@app.post("/api/connectors/{connector_id}/activate")
async def activate_connector(connector_id: str):
    """Activate a connector for scheduled syncs."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT sync_schedule FROM connectors WHERE id = ?", (connector_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Connector not found")

        cursor.execute(
            "UPDATE connectors SET status = ? WHERE id = ?",
            ("active", connector_id),
        )
        conn.commit()

    return {
        "message": "Connector activated",
        "connector_id": connector_id,
        "status": "active",
        "sync_schedule": row[0],
    }


@app.post("/api/connectors/{connector_id}/deactivate")
async def deactivate_connector(connector_id: str):
    """Deactivate a connector."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM connectors WHERE id = ?", (connector_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Connector not found")

        cursor.execute(
            "UPDATE connectors SET status = ? WHERE id = ?",
            ("inactive", connector_id),
        )
        conn.commit()

    return {
        "message": "Connector deactivated",
        "connector_id": connector_id,
        "status": "inactive",
    }


# ============================================================================
# Sync Job Endpoints
# ============================================================================


@app.post("/api/connectors/{connector_id}/sync")
async def trigger_sync(
    connector_id: str,
    sync_mode: str | None = None,
    triggered_by: str | None = None,
):
    """Trigger a manual sync for a connector.

    This starts a background sync job that extracts data from the
    configured source and loads it into the system.
    """
    # Get connector
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM connectors WHERE id = ?", (connector_id,))
        connector = cursor.fetchone()

    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    mode = sync_mode or connector["sync_mode"]

    # Check if there's already a running job for this connector
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM sync_jobs WHERE connector_id = ? AND status = 'running'",
            (connector_id,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="A sync job is already running for this connector",
            )

    # Try to use the worker for actual execution
    try:
        from scheduler.worker import execute_sync_job
        from scheduler.jobs import JobType

        job_id = execute_sync_job(
            connector_id=connector_id,
            job_type=JobType.MANUAL,
            sync_mode=mode,
            triggered_by=triggered_by,
        )

        return {
            "job_id": job_id,
            "connector_id": connector_id,
            "connector_name": connector["name"],
            "sync_mode": mode,
            "status": "running",
            "message": "Sync job started in background",
        }

    except ImportError:
        # Fallback: create job record without execution
        job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sync_jobs
                    (id, connector_id, job_type, sync_mode, status, started_at, triggered_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, connector_id, "manual", mode, "pending", now, triggered_by),
            )
            conn.commit()

        return {
            "job_id": job_id,
            "connector_id": connector_id,
            "connector_name": connector["name"],
            "sync_mode": mode,
            "status": "pending",
            "message": "Sync job created. Install APScheduler for background execution.",
        }


@app.get("/api/sync-jobs")
async def list_sync_jobs(
    connector_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List sync jobs with optional filters."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT j.*, c.name as connector_name
            FROM sync_jobs j
            LEFT JOIN connectors c ON j.connector_id = c.id
            WHERE 1=1
        """
        params: list[Any] = []

        if connector_id:
            query += " AND j.connector_id = ?"
            params.append(connector_id)

        if status:
            query += " AND j.status = ?"
            params.append(status)

        query += " ORDER BY j.started_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

    jobs = []
    for row in rows:
        jobs.append(
            {
                "id": row["id"],
                "connector_id": row["connector_id"],
                "connector_name": row["connector_name"],
                "job_type": row["job_type"],
                "sync_mode": row["sync_mode"],
                "status": row["status"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "total_records": row["total_records"],
                "processed_records": row["processed_records"],
                "failed_records": row["failed_records"],
                "watermark_value": row["watermark_value"],
                "error_message": row["error_message"],
                "triggered_by": row["triggered_by"],
            }
        )

    return {"jobs": jobs, "total": len(jobs), "limit": limit, "offset": offset}


@app.get("/api/sync-jobs/{job_id}")
async def get_sync_job(job_id: str):
    """Get sync job details."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT j.*, c.name as connector_name
            FROM sync_jobs j
            LEFT JOIN connectors c ON j.connector_id = c.id
            WHERE j.id = ?
            """,
            (job_id,),
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Sync job not found")

    return {
        "id": row["id"],
        "connector_id": row["connector_id"],
        "connector_name": row["connector_name"],
        "job_type": row["job_type"],
        "sync_mode": row["sync_mode"],
        "status": row["status"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "total_records": row["total_records"],
        "processed_records": row["processed_records"],
        "failed_records": row["failed_records"],
        "watermark_value": row["watermark_value"],
        "error_message": row["error_message"],
        "triggered_by": row["triggered_by"],
    }


@app.post("/api/sync-jobs/{job_id}/cancel")
async def cancel_sync_job(job_id: str):
    """Cancel a running or pending sync job."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM sync_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Sync job not found")

        if row[0] not in ("pending", "running"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job with status: {row[0]}",
            )

    # Try to use worker's cancel method for running jobs
    cancelled = False
    if row[0] == "running":
        try:
            from scheduler.worker import get_worker

            worker = get_worker()
            cancelled = worker.cancel_sync(job_id)
        except ImportError:
            pass

    # Fallback to direct database update
    if not cancelled:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sync_jobs SET status = ?, completed_at = ?, error_message = ? WHERE id = ?",
                ("cancelled", now, "Cancelled by user", job_id),
            )
            conn.commit()

    return {"message": "Sync job cancelled", "job_id": job_id, "status": "cancelled"}


@app.get("/api/sync-jobs/{job_id}/logs")
async def get_sync_job_logs(
    job_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Get logs for a sync job."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Verify job exists
        cursor.execute("SELECT id FROM sync_jobs WHERE id = ?", (job_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Sync job not found")

        cursor.execute(
            """
            SELECT * FROM sync_job_logs
            WHERE job_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (job_id, limit, offset),
        )
        rows = cursor.fetchall()

    logs = []
    for row in rows:
        logs.append(
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "level": row["level"],
                "message": row["message"],
                "context": safe_json_loads(row["context"], {}),
            }
        )

    return {"job_id": job_id, "logs": logs, "total": len(logs)}


# === Config Export/Import Endpoints ===


@app.post("/api/connectors/config/export")
async def export_connector_config(
    connector_ids: list[str] | None = None,
    format: str = Query(default="yaml", regex="^(yaml|json)$"),
):
    """Export connector configurations to YAML or JSON.

    If connector_ids is provided, only those connectors are exported.
    Otherwise, all connectors are exported.

    Returns the config file content as a downloadable response.
    """

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if connector_ids:
            placeholders = ",".join(["?"] * len(connector_ids))
            cursor.execute(
                f"SELECT * FROM connectors WHERE id IN ({placeholders})",
                connector_ids,
            )
        else:
            cursor.execute("SELECT * FROM connectors")

        rows = cursor.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No connectors found to export")

    # Build export data
    connectors = []
    for row in rows:
        config = safe_json_loads(row["connection_config"], {})

        # Remove sensitive fields from export
        sensitive_fields = [
            "password",
            "secret_access_key",
            "account_key",
            "api_key",
            "bearer_token",
            "client_secret",
            "private_key",
            "sas_token",
        ]
        for field in sensitive_fields:
            if field in config:
                config[field] = "${" + field.upper() + "}"  # Placeholder for env var

        connectors.append(
            {
                "name": row["name"],
                "type": row["connector_type"],
                "subtype": row["subtype"],
                "data_type": row["data_type"],
                "sync_mode": row["sync_mode"],
                "schedule": row["sync_schedule"],
                "batch_size": row["batch_size"],
                "connection": config,
            }
        )

    export_data = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "connectors": connectors,
    }

    if format == "yaml":
        import yaml

        content = yaml.dump(export_data, default_flow_style=False, sort_keys=False)
        media_type = "application/x-yaml"
        filename = "connectors.yaml"
    else:
        content = json.dumps(export_data, indent=2)
        media_type = "application/json"
        filename = "connectors.json"

    from fastapi.responses import Response

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/api/connectors/config/import")
async def import_connector_config(
    file: UploadFile = File(...),
    dry_run: bool = Query(
        default=True, description="Validate only, don't create connectors"
    ),
    overwrite: bool = Query(
        default=False, description="Overwrite existing connectors with same name"
    ),
):
    """Import connector configurations from YAML or JSON file.

    Use dry_run=true to validate the config without creating connectors.
    Use overwrite=true to update existing connectors with the same name.
    """
    from connectors.config_loader import ConfigLoader, ConfigValidationError

    # Read file content
    content = await file.read()

    # Detect format from filename or try both
    filename = file.filename or ""
    if filename.endswith(".yaml") or filename.endswith(".yml"):
        import yaml

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)[:200]}")
    elif filename.endswith(".json"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)[:200]}")
    else:
        # Try YAML first, then JSON
        import yaml

        try:
            data = yaml.safe_load(content)
        except Exception:
            try:
                data = json.loads(content)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Could not parse file as YAML or JSON"
                )

    # Validate configuration
    loader = ConfigLoader()
    try:
        connector_configs = loader._parse_config(data, filename)
    except ConfigValidationError as e:
        raise HTTPException(
            status_code=400, detail={"message": str(e), "errors": e.errors}
        )

    if dry_run:
        return {
            "status": "validated",
            "message": f"Successfully validated {len(connector_configs)} connector(s)",
            "connectors": [
                {
                    "name": c.name,
                    "type": c.connector_type.value,
                    "subtype": c.subtype.value,
                    "data_type": c.data_type.value,
                }
                for c in connector_configs
            ],
        }

    # Import connectors
    results = {"created": [], "updated": [], "skipped": [], "errors": []}

    for config in connector_configs:
        try:
            # Check if connector with same name exists
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM connectors WHERE name = ?", (config.name,)
                )
                existing = cursor.fetchone()

            if existing:
                if overwrite:
                    # Update existing connector
                    connector_id = existing[0]
                    now = datetime.utcnow().isoformat()

                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE connectors SET
                                connector_type = ?,
                                subtype = ?,
                                data_type = ?,
                                connection_config = ?,
                                sync_schedule = ?,
                                sync_mode = ?,
                                batch_size = ?
                            WHERE id = ?
                            """,
                            (
                                config.connector_type.value,
                                config.subtype.value,
                                config.data_type.value,
                                json.dumps(config.connection_config),
                                config.sync_schedule,
                                config.sync_mode.value,
                                config.batch_size,
                                connector_id,
                            ),
                        )
                        conn.commit()

                    results["updated"].append({"name": config.name, "id": connector_id})
                else:
                    results["skipped"].append(
                        {
                            "name": config.name,
                            "reason": "Connector with this name already exists",
                        }
                    )
            else:
                # Create new connector
                connector_id = str(uuid.uuid4())
                now = datetime.utcnow().isoformat()

                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO connectors
                            (id, name, connector_type, subtype, data_type,
                             connection_config, sync_schedule, sync_mode,
                             batch_size, status, created_at, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            connector_id,
                            config.name,
                            config.connector_type.value,
                            config.subtype.value,
                            config.data_type.value,
                            json.dumps(config.connection_config),
                            config.sync_schedule,
                            config.sync_mode.value,
                            config.batch_size,
                            "inactive",
                            now,
                            config.created_by or "config_import",
                        ),
                    )
                    conn.commit()

                results["created"].append({"name": config.name, "id": connector_id})

        except Exception as e:
            results["errors"].append({"name": config.name, "error": str(e)})

    return {
        "status": "completed",
        "message": f"Imported {len(results['created'])} new, updated {len(results['updated'])}, skipped {len(results['skipped'])}",
        "results": results,
    }


@app.post("/api/connectors/config/validate")
async def validate_connector_config(config: dict):
    """Validate a connector configuration without creating it.

    Useful for validating config before saving or submitting.
    """
    from connectors.config_loader import ConfigLoader, ConfigValidationError

    loader = ConfigLoader()
    try:
        # Wrap single config in list format
        configs = loader._parse_config(config, "inline")

        return {
            "valid": True,
            "message": "Configuration is valid",
            "connector": {
                "name": configs[0].name,
                "type": configs[0].connector_type.value,
                "subtype": configs[0].subtype.value,
                "data_type": configs[0].data_type.value,
            },
        }

    except ConfigValidationError as e:
        return {
            "valid": False,
            "message": str(e),
            "errors": e.errors,
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
