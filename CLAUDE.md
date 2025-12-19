# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Healthcare Payment Integrity Prototype - a local-first fraud detection system for healthcare claims using FastAPI, ChromaDB for RAG, and Claude API for intelligent explanations.

## Common Commands

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
make lint          # Check only
make lint-fix      # Auto-fix

# Download CMS reference data
make data-all      # All data (~10 min)
make data-ncci     # NCCI PTP/MUE edits
make data-mpfs     # Medicare fee schedule
make data-lcd      # LCD coverage
make data-leie     # OIG exclusion list
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

PRs trigger: Ruff linting (required), pytest (required), mypy (advisory), bandit security scan (advisory).

## Environment Variables

- `ANTHROPIC_API_KEY` - Required for Claude explanations (gracefully degrades without it)
- `DB_PATH` - SQLite database path (default: `./data/prototype.db`)
- `CHROMA_PERSIST_DIR` - ChromaDB storage (default: `./data/chroma`)
