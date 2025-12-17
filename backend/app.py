"""FastAPI backend for Healthcare Payment Integrity prototype."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rules import evaluate_baseline, ThresholdConfig
from rag import get_store
from claude_client import get_fraud_explanation


# Database setup
DB_PATH = os.getenv("DB_PATH", "./data/prototype.db")


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

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
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
async def analyze_claim(job_id: str, claim: ClaimSubmission):
    """Run fraud analysis on a claim."""

    # Load reference datasets
    datasets = load_datasets()

    # Convert claim to dict for rules engine
    claim_dict = {
        "claim_id": claim.claim_id,
        "billed_amount": claim.billed_amount or sum(i.line_amount for i in claim.items),
        "diagnosis_codes": claim.diagnosis_codes,
        "items": [item.model_dump() for item in claim.items],
        "provider": claim.provider or {},
        "member": claim.member or {},
    }

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

    # Get Claude explanation
    claude_result = get_fraud_explanation(
        claim=claim_dict,
        rule_hits=outcome.rule_result.hits,
        fraud_score=outcome.decision.score,
        decision_mode=outcome.decision.decision_mode,
        rag_context=rag_context,
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

    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "avg_fraud_score": round(avg_score, 3),
        "rag_documents": get_store().count(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
