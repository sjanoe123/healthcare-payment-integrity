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
- **Rules engine**: `backend/rules/` - 54+ fraud detection rules organized by category
  - `engine.py` - Core evaluation logic, aggregates rule hits into `BaselineOutcome`
  - `models.py` - `RuleHit`, `RuleContext`, `BaselineOutcome` dataclasses
  - `registry.py` - Rule registration system
  - `thresholds.py` - Score thresholds and decision modes
  - `categories/` - Rule implementations organized by category:
    - `format_rules.py` - Field validation, date/code format checks
    - `eligibility_rules.py` - Member eligibility, coverage, auth requirements
    - `timely_filing_rules.py` - Filing deadline validation
    - `duplicate_rules.py` - Duplicate claim detection
    - `cob_rules.py` - Coordination of benefits
    - `ncci_rules.py` - NCCI PTP, MUE, add-on code edits
    - `modifier_rules.py` - Modifier validation and abuse detection
    - `pos_rules.py` - Place of service validation
    - `pricing_rules.py` - Fee schedule and pricing checks
    - `necessity_rules.py` - Medical necessity and frequency limits
    - `fwa_rules.py` - Fraud, waste, abuse patterns
    - `oce_rules.py` - Outpatient code editor rules
    - `specialty_rules.py` - Specialty-specific rules (dental, DME, telehealth)
    - `surgical_rules.py` - Global period, multiple procedure rules
    - `coverage_rules.py` - LCD/NCD coverage validation
- **Shared utilities**: `backend/utils/`
  - `date_parser.py` - Flexible date parsing with validation
- **RAG**: `backend/rag/chroma_store.py` - ChromaDB wrapper for policy document retrieval
- **Claude integration**: `backend/claude_client.py` - Kirk AI analysis with structured JSON responses
- **Kirk config**: `backend/kirk_config.py` - Kirk AI personality, prompts, and category-specific guidance

### Frontend (React + TypeScript)

- **Entry point**: `frontend/src/main.tsx` - React app with React Query
- **Pages**: `frontend/src/pages/`
  - `Dashboard.tsx` - Overview with stats, charts (Recharts), and system status
  - `AnalyzeClaim.tsx` - Claim submission and analysis
  - `ClaimHistory.tsx` - List of analyzed claims with pagination
  - `PolicySearch.tsx` - RAG-powered policy document search
- **Components**: `frontend/src/components/`
  - `kirk/` - Kirk AI avatar, messages, thinking animation, follow-up chat
  - `analysis/` - FraudScoreGauge, ResultsDisplay
  - `layout/` - AppLayout, Sidebar (with mobile drawer), Header
  - `charts/` - SavingsChart, CategoryPieChart with accessibility support
- **API**: `frontend/src/api/`
  - `client.ts` - Axios client with interceptors
  - `hooks/` - React Query hooks (useStats, useHealth, useJobs, etc.)
  - `types.ts` - TypeScript types including Kirk structured response interfaces
- **Utilities**: `frontend/src/utils/`
  - `mockData.ts` - Demo mode data with dynamic date generation

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

Rules return `RuleHit` objects with weights that adjust the fraud score. Organized by category:

| Category | Rules | Examples |
|----------|-------|----------|
| Format | 3 | `FORMAT_MISSING_FIELD`, `FORMAT_INVALID_DATE`, `FORMAT_INVALID_CODE` |
| Eligibility | 4 | `ELIGIBILITY_INACTIVE`, `ELIGIBILITY_NON_COVERED`, `ELIGIBILITY_LIMIT_EXCEEDED`, `ELIGIBILITY_NO_AUTH` |
| Timely Filing | 3 | `TIMELY_FILING_LATE`, `TIMELY_FILING_WARNING`, `TIMELY_FILING_NO_EXCEPTION` |
| Duplicate | 2 | `DUPLICATE_EXACT`, `DUPLICATE_LINE` |
| COB | 2 | `COB_WRONG_PRIMARY`, `COB_INCOMPLETE` |
| NCCI | 4 | `NCCI_PTP`, `NCCI_MUE`, `NCCI_ADDON_NO_PRIMARY`, `NCCI_MUTUALLY_EXCLUSIVE` |
| Modifier | 4 | `MODIFIER_INVALID`, `MODIFIER_MISSING`, `MODIFIER_59_ABUSE`, `MODIFIER_BILATERAL_CONFLICT` |
| POS | 2 | `POS_INVALID`, `POS_PROVIDER_MISMATCH` |
| Pricing | 2 | `PRICING_EXCEEDS_FEE`, `PRICING_UNITS_EXCEED` |
| Necessity | 3 | `NECESSITY_EXPERIMENTAL`, `NECESSITY_FREQUENCY_EXCEEDED`, `NECESSITY_FREQUENCY_TOO_SOON` |
| FWA | 3 | `OIG_EXCLUSION`, `FWA_WATCH`, `FWA_VOLUME_SPIKE` |
| OCE | 1 | `OCE_INPATIENT_ONLY` |
| Coverage | 4 | `LCD_MISMATCH`, `LCD_AGE_CONFLICT`, `LCD_GENDER_CONFLICT`, `LCD_EXPERIMENTAL` |
| Specialty | 2 | `SPECIALTY_TELEHEALTH_NOT_ELIGIBLE`, `SPECIALTY_UNBUNDLING` |
| Surgical | 5 | `SURGICAL_GLOBAL_PERIOD`, `SURGICAL_MULTIPLE_NO_51`, `SURGICAL_ASSISTANT_NOT_ALLOWED`, `SURGICAL_COSURGEON_NOT_ALLOWED`, `SURGICAL_BILATERAL_*` |

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
- Recharts (dashboard charts)
- Framer Motion
- Axios
- Vitest + Testing Library

## Key Files

| File | Purpose |
|------|---------|
| `backend/app.py` | FastAPI routes and middleware |
| `backend/rules/engine.py` | Fraud scoring logic |
| `backend/rules/categories/` | Rule implementations by category |
| `backend/utils/date_parser.py` | Shared date parsing utility |
| `backend/claude_client.py` | Kirk AI integration with structured responses |
| `backend/kirk_config.py` | Kirk AI personality and prompts |
| `backend/railway.json` | Railway deployment config |
| `frontend/src/App.tsx` | React router setup |
| `frontend/src/api/client.ts` | API client with error handling |
| `frontend/src/api/types.ts` | TypeScript types including Kirk response interfaces |
| `frontend/src/components/kirk/KirkChat.tsx` | Kirk chat with follow-up support |
| `frontend/src/components/charts/` | Dashboard charts (SavingsChart, CategoryPieChart) |
| `frontend/src/utils/mockData.ts` | Demo mode data generation |
| `frontend/vercel.json` | Vercel SPA routing config |

## Kirk AI Features

Kirk is the AI-powered claims analysis assistant using Claude Sonnet 4.5.

### Structured JSON Response Format

Kirk responds with structured JSON for consistent parsing:

```json
{
  "risk_summary": "2-3 sentence executive summary",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "chain_of_thought": "Step-by-step reasoning",
  "findings": [
    {
      "category": "ncci|coverage|provider|financial|format|modifier|eligibility",
      "issue": "Specific finding",
      "evidence": "Supporting detail",
      "regulation": "CFR/CMS citation",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW"
    }
  ],
  "recommendations": [
    {"priority": 1, "action": "Recommended action", "rationale": "Why"}
  ],
  "confidence": 0.85
}
```

### Category-Specific Analysis

Kirk provides focused analysis based on the primary rule category:
- `ncci` - NCCI column 1/2 relationships, modifier indicators, MUE limits
- `coverage` - LCD/NCD compliance, diagnosis support, frequency limits
- `provider` - OIG exclusions, credentials, billing patterns
- `financial` - Fee schedule benchmarks, outlier detection, unbundling
- `modifier` - Modifier validity, 59/X usage, bilateral conflicts
- `eligibility` - Member coverage, benefit limits, prior authorization

### Follow-up Conversations

KirkChat supports follow-up questions with context-aware responses about:
- Why specific flags were raised
- Recommended next steps
- NCCI/PTP/MUE details
- Appeal and denial guidance
- Provider and OIG concerns
