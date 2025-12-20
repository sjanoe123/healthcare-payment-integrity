# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Healthcare Payment Integrity Prototype - a fraud detection system for healthcare claims using FastAPI, ChromaDB for RAG, and Claude API for intelligent explanations. Features a React frontend with Kirk AI assistant.

## Deployments

| Environment | URL | Platform |
|-------------|-----|----------|
| Frontend | https://healthcare-payment-integrity.vercel.app | Vercel |
| Backend API | https://healthcare-payment-integrity-api-production.up.railway.app | Railway |

## Common Commands

### Backend
```bash
# Install dependencies
make install

# Run backend (port 8080)
make run

# Seed ChromaDB with policy documents
make seed

# Run unit tests
PYTHONPATH=backend pytest tests/ -v

# Run a single test
PYTHONPATH=backend pytest tests/test_rules.py::test_function_name -v

# Run integration tests (requires running server)
make test-integration

# Linting
make lint          # Check only (ruff check + ruff format --check)
make lint-fix      # Auto-fix

# Download CMS reference data
make data-all      # All data (~10 min)
make data-ncci     # NCCI PTP/MUE edits
make data-mpfs     # Medicare fee schedule
make data-lcd      # LCD coverage
make data-leie     # OIG exclusion list
```

### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Development server (port 5173)
npm run dev

# Build for production
npm run build

# Run tests
npm run test        # Watch mode
npm run test:run    # Single run

# Linting
npm run lint
```

## Architecture

### Backend (FastAPI)

- **Entry point**: `backend/app.py` - FastAPI application with SQLite persistence
- **Rules engine**: `backend/rules/` - 13 fraud detection rules evaluated via `evaluate_baseline()`
  - `engine.py` - Core evaluation logic, aggregates rule hits into `BaselineOutcome`
  - `ruleset.py` - Individual rule implementations (NCCI, LCD, OIG, etc.)
  - `models.py` - `RuleHit`, `RuleContext`, `BaselineOutcome` dataclasses
  - `registry.py` - Rule registration system
  - `thresholds.py` - Score thresholds and decision modes
- **RAG**: `backend/rag/chroma_store.py` - ChromaDB wrapper for policy document retrieval
- **Claude integration**: `backend/claude_client.py` - Generates fraud explanations using Claude Haiku
- **Kirk config**: `backend/kirk_config.py` - Kirk AI assistant personality and prompts

### Frontend (React + TypeScript)

- **Entry point**: `frontend/src/main.tsx` - React app with React Query
- **Pages**: `frontend/src/pages/`
  - `Dashboard.tsx` - Overview with stats and system status
  - `AnalyzeClaim.tsx` - Claim submission and analysis
  - `ClaimHistory.tsx` - List of analyzed claims with pagination
  - `PolicySearch.tsx` - RAG-powered policy document search
- **Components**: `frontend/src/components/`
  - `kirk/` - Kirk AI avatar, messages, thinking animation
  - `analysis/` - FraudScoreGauge, ResultsDisplay
  - `layout/` - AppLayout, Sidebar, Header
- **API**: `frontend/src/api/`
  - `client.ts` - Axios client with interceptors
  - `hooks/` - React Query hooks (useStats, useHealth, useJobs, etc.)
  - `types.ts` - TypeScript types and utility functions

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check with RAG document count |
| POST | `/api/upload` | Submit claim, create job |
| POST | `/api/analyze/{job_id}` | Run fraud analysis on claim |
| GET | `/api/results/{job_id}` | Get analysis results |
| GET | `/api/jobs?limit=100&offset=0` | List analyzed claims (paginated) |
| GET | `/api/stats` | Dashboard statistics |
| POST | `/api/search` | RAG policy document search |

### Data Flow

1. Claim submitted via POST `/api/upload` -> creates job
2. Analysis triggered via POST `/api/analyze/{job_id}` with claim data
3. Rules engine evaluates claim against datasets (NCCI, LCD, MPFS, OIG)
4. RAG searches relevant policy documents from ChromaDB
5. Claude generates explanation from rule hits + RAG context
6. Results stored in SQLite, returned as `AnalysisResult`

### Reference Datasets

Stored in `data/` directory as JSON files:
- `ncci_ptp.json` - NCCI Procedure-to-Procedure edits (29K+ code pairs)
- `ncci_mue.json` - NCCI Medically Unlikely Edits (8K+ codes)
- `mpfs.json` - Medicare Physician Fee Schedule rates
- `lcd.json` - Local Coverage Determination policies
- `oig_exclusions.json` - OIG excluded provider NPIs

### Fraud Detection Rules

Rules return `RuleHit` objects with weights that adjust the fraud score:
- **NCCI rules**: `NCCI_PTP` (procedure conflicts), `NCCI_MUE` (quantity limits)
- **Coverage rules**: `LCD_MISMATCH`, `LCD_AGE_CONFLICT`, `LCD_GENDER_CONFLICT`, `LCD_EXPERIMENTAL`
- **Provider rules**: `OIG_EXCLUSION`, `FWA_WATCH`, high-risk specialty flags
- **Financial rules**: `HIGH_DOLLAR`, `REIMB_OUTLIER`, `DUPLICATE_LINE`, `UTIL_OUTLIER`

## CI/CD

### GitHub Actions (`.github/workflows/ci.yml`)

**Backend job:**
- Ruff linting (`ruff check . && ruff format --check .`) - required
- pytest - required
- mypy - advisory
- bandit security scan - advisory

**Frontend job:**
- ESLint (`npm run lint`) - required
- TypeScript build (`npm run build`) - required
- Vitest (`npm run test:run`) - required

### Deployment

- **Frontend**: Auto-deploys to Vercel on push to main
- **Backend**: Deploy via Railway CLI:
  ```bash
  cd backend
  railway up --service healthcare-payment-integrity-api
  ```

## Environment Variables

### Backend (Railway)
- `ANTHROPIC_API_KEY` - Required for Claude explanations (gracefully degrades without it)
- `DB_PATH` - SQLite database path (default: `/data/prototype.db`)
- `CHROMA_PERSIST_DIR` - ChromaDB storage (default: `/data/chroma`)

### Frontend (Vercel)
- `VITE_API_URL` - Backend API URL (default: `http://localhost:8080`)

## Tech Stack

### Backend
- Python 3.12
- FastAPI + Uvicorn
- SQLite (embedded)
- ChromaDB (embedded vector store)
- Anthropic Claude API

### Frontend
- React 19 + TypeScript
- Vite 7
- TailwindCSS 3
- TanStack Query (React Query)
- Framer Motion
- Axios
- Vitest + Testing Library

## Key Files

| File | Purpose |
|------|---------|
| `backend/app.py` | FastAPI routes and middleware |
| `backend/rules/engine.py` | Fraud scoring logic |
| `backend/kirk_config.py` | Kirk AI personality |
| `backend/railway.json` | Railway deployment config |
| `frontend/src/App.tsx` | React router setup |
| `frontend/src/api/client.ts` | API client with error handling |
| `frontend/vercel.json` | Vercel SPA routing config |
