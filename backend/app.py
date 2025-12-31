"""FastAPI backend for Healthcare Payment Integrity prototype."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
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
from mapping import normalize_claim, denormalize_for_rules
from mapping.templates import get_template
from connectors.constants import CONNECTOR_SECRET_FIELDS

# Import all connectors at startup to trigger their registration with the registry.
# This ensures GET /api/connectors/types returns all available connector types.
# Without these imports, connectors only register when first used (lazy loading).
from connectors.database import PostgreSQLConnector, MySQLConnector, SQLServerConnector  # noqa: F401
from connectors.file import S3Connector, SFTPConnector, AzureBlobConnector  # noqa: F401

from routes import policies_router, mappings_router, rules_router, audit_router
from routes.audit import log_audit_event, AuditAction
from utils import sanitize_filename
from config import DB_PATH
from schemas import SemanticMatchRequest
from templates import (
    get_template_list,
    get_template as get_connector_template,
    apply_template,
)

# Configure logging
logger = logging.getLogger(__name__)

# Pagination limits
DEFAULT_JOBS_LIMIT = 100
MAX_JOBS_LIMIT = 1000

# Sample analysis configuration
# Maximum number of claims to analyze in a single sample request
# Limited to prevent long-running requests and excessive API usage
MAX_SAMPLE_ANALYSIS_SIZE = 10


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

        # ============================================================
        # Audit Logging Table (HIPAA Compliance)
        # ============================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                user_id TEXT,
                user_email TEXT,
                resource_type TEXT,
                resource_id TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                status TEXT DEFAULT 'success',
                error_message TEXT
            )
        """)

        # Audit indices for efficient querying
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type, resource_id)"
        )

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
        from scheduler import start_scheduler, shutdown_scheduler, execute_sync_job
        from scheduler.worker import JobType

        scheduler = start_scheduler(DB_PATH)
        logger.info("Scheduler started for background sync jobs")

        # Restore scheduled jobs for active connectors
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, sync_schedule FROM connectors WHERE status = 'active' AND sync_schedule IS NOT NULL"
                )
                active_connectors = cursor.fetchall()

            restored_count = 0
            for connector_id, sync_schedule in active_connectors:
                if sync_schedule:
                    try:
                        job_id = f"sync_{connector_id}"
                        scheduler.add_job(
                            job_id=job_id,
                            func=execute_sync_job,
                            cron_expression=sync_schedule,
                            kwargs={
                                "connector_id": connector_id,
                                "job_type": JobType.SCHEDULED,
                                "sync_mode": "incremental",
                                "triggered_by": "scheduler",
                            },
                            replace_existing=True,
                        )
                        restored_count += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to restore job for connector {connector_id}: {e}"
                        )

            if restored_count > 0:
                logger.info(f"Restored {restored_count} scheduled sync jobs")
        except Exception as e:
            logger.warning(f"Failed to restore scheduled jobs: {e}")

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
    "http://localhost:3000",
    "http://127.0.0.1:3000",
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

# Register API routers
app.include_router(policies_router)
app.include_router(mappings_router)
app.include_router(rules_router)
app.include_router(audit_router)


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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
            (job_id, claim.claim_id, "pending", datetime.now(timezone.utc).isoformat()),
        )

        # Audit log: claim uploaded
        log_audit_event(
            conn,
            action=AuditAction.CLAIM_UPLOAD.value,
            resource_type="claim",
            resource_id=claim.claim_id,
            details={"job_id": job_id, "items_count": len(claim.items)},
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

    # Get RAG policy context BEFORE rules evaluation
    policy_docs: list[dict] = []
    rag_context = None
    store = get_store()
    if store.count() > 0:
        # Multi-faceted search for relevant policy context
        procedure_codes = [i.procedure_code for i in claim.items]
        diagnosis_codes = (
            claim.diagnosis_codes if hasattr(claim, "diagnosis_codes") else []
        )

        # Search for procedure code coverage
        if procedure_codes:
            proc_query = f"CPT procedure codes {', '.join(set(procedure_codes))} coverage billing guidelines"
            proc_results = store.search(proc_query, n_results=3)
            policy_docs.extend(proc_results)

        # Search for diagnosis-related policies
        if diagnosis_codes:
            diag_query = f"ICD-10 diagnosis {', '.join(diagnosis_codes[:5])} medical necessity coverage"
            diag_results = store.search(diag_query, n_results=2)
            policy_docs.extend(diag_results)

        # Deduplicate by document ID
        seen_ids = set()
        unique_docs = []
        for doc in policy_docs:
            doc_id = doc.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                unique_docs.append(doc)
        policy_docs = unique_docs

        # Build RAG context string for Kirk
        if policy_docs:
            rag_context = "\n\n".join(
                f"[{r['metadata'].get('source', 'Policy')}]: {r['content'][:500]}..."
                for r in policy_docs[:5]  # Limit context for Kirk
            )

    # Denormalize OMOP fields to rules engine field names
    # (e.g., procedure_source_value -> procedure_code)
    rules_claim = denormalize_for_rules(claim_dict)

    # Run rules engine with policy context
    outcome = evaluate_baseline(
        claim=rules_claim,
        datasets=datasets,
        config={"base_score": 0.5},
        threshold_config=ThresholdConfig(),
        policy_docs=policy_docs,  # Pass RAG context to rules
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
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        cursor.execute(
            "UPDATE jobs SET status = ?, completed_at = ? WHERE job_id = ?",
            ("completed", datetime.now(timezone.utc).isoformat(), job_id),
        )

        # Audit log: claim analyzed
        log_audit_event(
            conn,
            action=AuditAction.CLAIM_ANALYZE.value,
            resource_type="claim",
            resource_id=claim.claim_id,
            details={
                "job_id": job_id,
                "fraud_score": outcome.decision.score,
                "decision_mode": outcome.decision.decision_mode,
                "rule_hits_count": len(outcome.rule_result.hits),
            },
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


# ============================================================
# Mapping Endpoints (Rate-Limited)
# Non-rate-limited mapping endpoints are in routes/mappings.py
# ============================================================


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
# Jobs & Claims Endpoints
# ============================================================================


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

# CONNECTOR_SECRET_FIELDS imported from connectors.constants


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
    now = datetime.now(timezone.utc).isoformat()

    # Extract and encrypt secrets
    config = request.connection_config.copy()
    secret_fields = CONNECTOR_SECRET_FIELDS.get(request.connector_type, [])

    # Encrypt and store secrets - fail loudly if encryption not configured
    cred_manager = get_credential_manager(DB_PATH)
    if not cred_manager.encryption_enabled:
        raise HTTPException(
            status_code=500,
            detail="Credential encryption not configured. "
            "Set CREDENTIAL_ENCRYPTION_KEY environment variable.",
        )

    try:
        config = cred_manager.extract_and_store_secrets(
            connector_id, config, secret_fields
        )
    except Exception as e:
        logger.error(f"Credential encryption failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to encrypt credentials: {str(e)[:100]}",
        )

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

            # Audit log: connector created
            log_audit_event(
                conn,
                action=AuditAction.CONNECTOR_CREATE.value,
                user_id=request.created_by,
                resource_type="connector",
                resource_id=connector_id,
                details={
                    "name": request.name,
                    "connector_type": request.connector_type,
                    "subtype": request.subtype,
                    "data_type": request.data_type,
                },
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

        # Encrypt and store secrets - fail loudly if encryption not configured
        cred_manager = get_credential_manager(DB_PATH)
        if not cred_manager.encryption_enabled:
            raise HTTPException(
                status_code=500,
                detail="Credential encryption not configured. "
                "Set CREDENTIAL_ENCRYPTION_KEY environment variable.",
            )

        try:
            config = cred_manager.extract_and_store_secrets(
                connector_id, config, secret_fields
            )
        except Exception as e:
            logger.error(f"Credential encryption failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to encrypt credentials: {str(e)[:100]}",
            )

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

        # Audit log: connector deleted
        log_audit_event(
            conn,
            action=AuditAction.CONNECTOR_DELETE.value,
            resource_type="connector",
            resource_id=connector_id,
        )

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
    """Test a file system connection.

    Uses a connector class lookup to reduce code duplication.
    """
    # Connector class mapping for file subtypes
    FILE_CONNECTOR_CLASSES = {
        "s3": "S3Connector",
        "sftp": "SFTPConnector",
        "azure_blob": "AzureBlobConnector",
    }

    if subtype not in FILE_CONNECTOR_CLASSES:
        return {
            "success": False,
            "message": f"File subtype '{subtype}' not yet implemented",
            "latency_ms": None,
            "details": {"subtype": subtype},
        }

    try:
        # Dynamic import of the connector class
        from connectors import file as file_connectors

        connector_class_name = FILE_CONNECTOR_CLASSES[subtype]
        connector_class = getattr(file_connectors, connector_class_name)

        connector = connector_class(
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

    except ImportError as e:
        return {
            "success": False,
            "message": f"Missing dependency: {e}",
            "latency_ms": None,
            "details": {"error": str(e), "subtype": subtype},
        }
    except AttributeError as e:
        return {
            "success": False,
            "message": f"Connector class not found: {e}",
            "latency_ms": None,
            "details": {"error": str(e), "subtype": subtype},
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)[:200]}",
            "latency_ms": None,
            "details": {"error_type": type(e).__name__},
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
    """Activate a connector for scheduled syncs.

    This updates the connector status and adds a scheduled job to APScheduler
    if a sync_schedule (cron expression) is configured.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT sync_schedule FROM connectors WHERE id = ?", (connector_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Connector not found")

        sync_schedule = row[0]

        cursor.execute(
            "UPDATE connectors SET status = ? WHERE id = ?",
            ("active", connector_id),
        )
        conn.commit()

    # Add scheduled job to APScheduler if schedule is configured
    scheduler_status = "no_schedule"
    if sync_schedule:
        try:
            from scheduler import get_scheduler, execute_sync_job
            from scheduler.worker import JobType

            scheduler = get_scheduler()
            if scheduler.is_running:
                job_id = f"sync_{connector_id}"
                scheduler.add_job(
                    job_id=job_id,
                    func=execute_sync_job,
                    cron_expression=sync_schedule,
                    kwargs={
                        "connector_id": connector_id,
                        "job_type": JobType.SCHEDULED,
                        "sync_mode": "incremental",
                        "triggered_by": "scheduler",
                    },
                    replace_existing=True,
                )
                scheduler_status = "scheduled"
                logger.info(
                    f"Added scheduled job for connector {connector_id}: {sync_schedule}"
                )
            else:
                scheduler_status = "scheduler_not_running"
                logger.warning(
                    f"Scheduler not running, cannot add job for {connector_id}"
                )
        except ImportError:
            scheduler_status = "scheduler_not_available"
            logger.warning("APScheduler not installed, scheduled sync not available")
        except Exception as e:
            scheduler_status = f"error: {str(e)[:100]}"
            logger.error(f"Failed to add scheduled job for {connector_id}: {e}")

    return {
        "message": "Connector activated",
        "connector_id": connector_id,
        "status": "active",
        "sync_schedule": sync_schedule,
        "scheduler_status": scheduler_status,
    }


@app.post("/api/connectors/{connector_id}/deactivate")
async def deactivate_connector(connector_id: str):
    """Deactivate a connector.

    This updates the connector status and removes any scheduled job
    from APScheduler.
    """
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

    # Remove scheduled job from APScheduler
    scheduler_status = "not_scheduled"
    try:
        from scheduler import get_scheduler

        scheduler = get_scheduler()
        if scheduler.is_running:
            job_id = f"sync_{connector_id}"
            if scheduler.remove_job(job_id):
                scheduler_status = "removed"
                logger.info(f"Removed scheduled job for connector {connector_id}")
            else:
                scheduler_status = "no_job_found"
        else:
            scheduler_status = "scheduler_not_running"
    except ImportError:
        scheduler_status = "scheduler_not_available"
    except Exception as e:
        scheduler_status = f"error: {str(e)[:100]}"
        logger.error(f"Failed to remove scheduled job for {connector_id}: {e}")

    return {
        "message": "Connector deactivated",
        "connector_id": connector_id,
        "status": "inactive",
        "scheduler_status": scheduler_status,
    }


@app.get("/api/scheduler/jobs")
async def list_scheduled_jobs():
    """List all scheduled sync jobs from APScheduler.

    Returns job details including next run time for each active connector.
    """
    try:
        from scheduler import get_scheduler

        scheduler = get_scheduler()
        if not scheduler.is_running:
            return {
                "scheduler_running": False,
                "jobs": [],
                "message": "Scheduler not running",
            }

        jobs = scheduler.get_jobs()
        return {
            "scheduler_running": True,
            "jobs": jobs,
            "total_jobs": len(jobs),
        }
    except ImportError as e:
        return {
            "scheduler_running": False,
            "jobs": [],
            "message": f"APScheduler not installed: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Failed to list scheduled jobs: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list jobs: {str(e)[:200]}"
        )


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

    except ImportError as e:
        logger.error(f"Failed to import scheduler modules: {e}")
        # Fallback: create job record without execution
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sync_jobs
                    (id, connector_id, job_type, sync_mode, status, started_at, triggered_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    connector_id,
                    "manual",
                    mode,
                    "pending",
                    now,
                    triggered_by,
                    now,
                ),
            )
            conn.commit()

        return {
            "job_id": job_id,
            "connector_id": connector_id,
            "connector_name": connector["name"],
            "sync_mode": mode,
            "status": "pending",
            "message": f"Sync job created but worker not available: {str(e)}",
        }

    except Exception as e:
        logger.error(f"Sync job execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Sync job execution failed: {str(e)[:200]}",
        )


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
        now = datetime.now(timezone.utc).isoformat()
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


# === Sample Analysis Endpoint ===


@app.post("/api/connectors/{connector_id}/sample-analysis")
async def analyze_connector_samples(
    connector_id: str,
    limit: int = Query(default=10, ge=1, le=100, alias="sample_size"),
):
    """Analyze a sample of claims from a connector in real-time.

    This endpoint:
    1. Connects directly to the connector's data source
    2. Fetches a sample of claims
    3. Runs fraud analysis on each claim using the rules engine
    4. Returns aggregated results with key findings

    No sync required - fetches and analyzes claims on demand.

    Args:
        connector_id: ID of the connector to analyze
        limit: Number of claims to analyze (1-100, default 10).
               Query parameter name is 'sample_size' for backward compatibility.

    Returns:
        JSON response with:
        - connector_id, connector_name: Connector identification
        - preview_mode: True if using synthetic data (connection failed)
        - summary: Risk level counts and average score
        - metrics: Analysis timing and claim counts
        - results: Array of claim analysis results

    Raises:
        HTTPException 404: Connector not found
        HTTPException 400: Non-PostgreSQL connector or invalid table name
    """
    # Local imports for functions not needed elsewhere.
    # PostgreSQLConnector uses top-level import (line 36) for connector registry.
    from connectors.database.base_db import quote_identifier, validate_identifier
    from rules.engine import evaluate_baseline
    from security.credentials import get_credential_manager

    # Verify connector exists
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM connectors WHERE id = ?", (connector_id,))
        connector = cursor.fetchone()

    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    connector_dict = dict(connector)
    config = safe_json_loads(connector_dict.get("connection_config", "{}"), {})

    # Inject secrets
    try:
        cred_manager = get_credential_manager()
        config = cred_manager.inject_secrets(connector_id, config, ["password"])
    except Exception as e:
        logger.warning(f"Failed to inject secrets: {e}")

    # Only PostgreSQL supported for now
    if connector_dict.get("subtype") != "postgresql":
        raise HTTPException(
            status_code=400,
            detail=f"Sample analysis only supports PostgreSQL connectors, got {connector_dict.get('subtype')}",
        )

    # Connect and fetch sample claims
    sample_results = []
    preview_mode = False
    claims_fetched = []
    db_connector = None

    try:
        db_connector = PostgreSQLConnector(
            connector_id=connector_id,
            name=connector_dict["name"],
            config=config,
        )
        db_connector.connect()
        logger.info(f"Connected to connector {connector_id} for sample analysis")

        # Sanitize table names to prevent SQL injection
        table = config.get("table", "claims")
        try:
            safe_table = quote_identifier(validate_identifier(table, "table name"))
            safe_claim_lines = quote_identifier("claim_lines")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid table name: {e}")

        # Build query with sanitized identifiers
        # Note: This query assumes a standard claims schema with claim_lines table.
        # Required schema:
        #   - claims table: claim_id (PK), member_id, billing_provider_npi,
        #     rendering_provider_npi, facility_npi, statement_from_date,
        #     statement_to_date, place_of_service, diagnosis_codes, total_charge,
        #     created_at
        #   - claim_lines table: claim_id (FK), line_number, procedure_code,
        #     modifier_1, modifier_2, units, charge_amount, diagnosis_pointer
        # Uses subquery pattern for PostgreSQL strict mode compatibility.
        query = f"""
            SELECT c.*,
                   (SELECT json_agg(json_build_object(
                       'line_number', cl.line_number,
                       'procedure_code', cl.procedure_code,
                       'modifier_1', cl.modifier_1,
                       'modifier_2', cl.modifier_2,
                       'units', cl.units,
                       'charge_amount', cl.charge_amount,
                       'diagnosis_pointer', cl.diagnosis_pointer
                   ))
                   FROM {safe_claim_lines} cl
                   WHERE cl.claim_id = c.claim_id) as items
            FROM {safe_table} c
            ORDER BY c.created_at DESC
            LIMIT {int(limit)}
        """
        claims_fetched = db_connector.execute_query(query)
        logger.info(
            f"Fetched {len(claims_fetched)} claims from connector {connector_id}"
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(
            f"Failed to fetch claims from connector {connector_id}: "
            f"{type(e).__name__}: {e}"
        )
        # Fall back to preview mode
        preview_mode = True
    finally:
        # Ensure connection is always closed
        if db_connector:
            try:
                db_connector.disconnect()
            except Exception:
                pass  # Ignore disconnect errors

    # Analyze each claim
    analysis_start = time.time()
    claims_failed = 0

    if claims_fetched:
        # Load reference datasets
        datasets = load_datasets()

        for claim_row in claims_fetched:
            try:
                # Transform to analysis format
                items = claim_row.get("items") or []
                if isinstance(items, str):
                    items = safe_json_loads(items, [])
                # Filter out null items from LEFT JOIN
                items = [i for i in items if i and i.get("procedure_code")]

                claim_data = {
                    "claim_id": claim_row.get("claim_id"),
                    "member_id": claim_row.get("member_id"),
                    "billing_npi": claim_row.get("billing_provider_npi"),
                    "rendering_npi": claim_row.get("rendering_provider_npi"),
                    "facility_npi": claim_row.get("facility_npi"),
                    "service_date": str(claim_row.get("statement_from_date", "")),
                    "service_end_date": str(claim_row.get("statement_to_date", "")),
                    "place_of_service": claim_row.get("place_of_service", "11"),
                    "diagnosis_codes": claim_row.get("diagnosis_codes") or [],
                    "total_charge": float(claim_row.get("total_charge") or 0),
                    "items": [
                        {
                            "line_number": i.get("line_number", idx + 1),
                            "procedure_code": i.get("procedure_code"),
                            "modifiers": [
                                m
                                for m in [i.get("modifier_1"), i.get("modifier_2")]
                                if m
                            ],
                            "units": i.get("units", 1),
                            "charge": float(i.get("charge_amount") or 0),
                        }
                        for idx, i in enumerate(items)
                    ],
                }

                # Run rules engine
                outcome = evaluate_baseline(claim_data, datasets)
                fraud_score = outcome.score
                rule_hits = [
                    {"rule_id": h.rule_id, "description": h.description}
                    for h in outcome.rule_hits
                ]

                if fraud_score >= 0.7:
                    risk_level = "high"
                elif fraud_score >= 0.4:
                    risk_level = "medium"
                else:
                    risk_level = "low"

                sample_results.append(
                    {
                        "claim_id": claim_data["claim_id"],
                        "fraud_score": round(fraud_score, 3),
                        "risk_level": risk_level,
                        "flags_count": len(rule_hits),
                        "top_flags": [h["rule_id"] for h in rule_hits[:3]],
                        "total_charge": claim_data["total_charge"],
                    }
                )

            except Exception as e:
                claims_failed += 1
                logger.warning(
                    f"Failed to analyze claim {claim_row.get('claim_id')} "
                    f"from connector {connector_id}: {type(e).__name__}: {e}"
                )
                continue

    # If no real results, generate preview data
    if not sample_results:
        preview_mode = True
        # Generate deterministic preview results based on connector ID
        # Note: MD5 is used here only for deterministic seeding of random data,
        # not for any security purpose. This ensures the same connector always
        # shows the same preview data for consistent demo experience.
        seed_hash = int(hashlib.md5(connector_id.encode()).hexdigest()[:8], 16)
        random.seed(seed_hash)

        for i in range(min(limit, MAX_SAMPLE_ANALYSIS_SIZE)):
            score = random.uniform(0.2, 0.95)
            flags = random.randint(0, 5)

            if score >= 0.7:
                risk_level = "high"
            elif score >= 0.4:
                risk_level = "medium"
            else:
                risk_level = "low"

            sample_results.append(
                {
                    "claim_id": f"PREVIEW-{connector_id[:8]}-{i + 1:03d}",
                    "fraud_score": round(score, 3),
                    "risk_level": risk_level,
                    "flags_count": flags,
                    "top_flags": random.sample(
                        [
                            "NCCI_CONFLICT",
                            "LCD_MISMATCH",
                            "HIGH_DOLLAR",
                            "DUPLICATE_LINE",
                            "OIG_EXCLUSION",
                            "MUE_EXCEEDED",
                        ],
                        min(flags, 3),
                    )
                    if flags > 0
                    else [],
                }
            )

    # Calculate summary statistics
    high_risk_count = sum(1 for r in sample_results if r["risk_level"] == "high")
    medium_risk_count = sum(1 for r in sample_results if r["risk_level"] == "medium")
    low_risk_count = sum(1 for r in sample_results if r["risk_level"] == "low")
    total_flags = sum(r["flags_count"] for r in sample_results)
    avg_score = (
        round(sum(r["fraud_score"] for r in sample_results) / len(sample_results), 3)
        if sample_results
        else 0
    )

    # Calculate analysis duration
    analysis_duration_ms = int((time.time() - analysis_start) * 1000)

    return {
        "connector_id": connector_id,
        "connector_name": connector_dict["name"],
        "status": "completed",
        "preview_mode": preview_mode,
        "sample_size": len(sample_results),
        "summary": {
            "high_risk": high_risk_count,
            "medium_risk": medium_risk_count,
            "low_risk": low_risk_count,
            "total_flags": total_flags,
            "avg_score": avg_score,
        },
        "metrics": {
            "analysis_duration_ms": analysis_duration_ms,
            "claims_fetched": len(claims_fetched),
            "claims_analyzed": len(sample_results),
            "claims_failed": claims_failed,
        },
        "results": sample_results,
        "message": (
            "Preview: Could not connect to data source. Showing sample results."
            if preview_mode
            else f"Analyzed {len(sample_results)} claims from live database. "
            f"{high_risk_count} high-risk claims detected."
        ),
    }


# === Quick Start Templates ===


@app.get("/api/templates")
async def list_templates(category: str | None = None):
    """List available connector templates for quick start.

    Templates provide pre-configured connector settings for common
    healthcare data sources like Epic, Cerner, and standard EDI formats.
    """
    templates = get_template_list()

    if category:
        templates = [t for t in templates if t.get("category") == category]

    # Group by category
    categories = {}
    for t in templates:
        cat = t.get("category", "general")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(t)

    return {
        "templates": templates,
        "categories": categories,
        "total": len(templates),
    }


@app.get("/api/templates/{template_id}")
async def get_template_detail(template_id: str):
    """Get detailed configuration for a specific template.

    Returns the full template configuration that can be used
    to create a new connector.
    """
    template = get_connector_template(template_id)
    if not template:
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        )

    return {
        "id": template_id,
        **template,
    }


@app.post("/api/templates/{template_id}/apply")
async def apply_template_to_connector(
    template_id: str,
    name: str = Query(..., description="Name for the new connector"),
    overrides: dict[str, Any] | None = None,
):
    """Create a new connector from a template.

    Applies the template configuration with optional overrides
    and creates a new connector entry in the database.
    """
    try:
        config = apply_template(template_id, overrides)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Create connector from template
    connector_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO connectors
                (id, name, connector_type, subtype, data_type, sync_mode,
                 connection_config, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connector_id,
                name,
                config.get("connector_type", "database"),
                config.get("subtype", ""),
                config.get("data_type", "claims"),
                config.get("sync_mode", "full"),
                json.dumps(config.get("connection_config", {})),
                "inactive",
                now,
                now,
            ),
        )
        conn.commit()

    return {
        "success": True,
        "connector_id": connector_id,
        "name": name,
        "template_id": template_id,
        "message": f"Connector created from template '{template_id}'",
    }


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
        "exported_at": datetime.now(timezone.utc).isoformat(),
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
    # Sanitize filename for safe extension detection
    filename = sanitize_filename(file.filename)
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
                    now = datetime.now(timezone.utc).isoformat()

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
                now = datetime.now(timezone.utc).isoformat()

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
