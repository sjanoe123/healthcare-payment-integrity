# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Healthcare Payment Integrity Prototype - a fraud detection system for healthcare claims using FastAPI, ChromaDB for RAG, and Claude API for intelligent explanations. Features a React frontend with Kirk AI assistant.

## Deployments

| Environment | URL | Platform |
|-------------|-----|----------|
| Frontend | https://healthcare-payment-integrity-glhr.vercel.app | Vercel |
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
- **Field mapping**: `backend/mapping/` - OMOP CDM-based schema normalization
  - `omop_schema.py` - Canonical OMOP CDM schema with 40+ field aliases
  - `mapper.py` - FieldMapper class for transforming claims to canonical format
  - `embeddings.py` - PubMedBERT-based semantic field matching for unknown fields
  - `templates/` - Pre-built mappings for EDI 837P, 837I, and CSV formats
- **Data source connectors**: `backend/connectors/` - External data integration framework
  - `base.py` - `BaseConnector` abstract class for all connectors
  - `models.py` - Pydantic models (ConnectorType, SyncMode, ConnectionTestResult)
  - `registry.py` - Connector type registry and factory
  - `database/` - Database connectors (PostgreSQL, MySQL) using SQLAlchemy
  - `file/` - File connectors (S3, SFTP) with EDI 837 and CSV parsers
- **Scheduler**: `backend/scheduler/` - Background job scheduling with APScheduler
  - `scheduler.py` - `SyncScheduler` wrapper with SQLite persistence
  - `jobs.py` - `SyncJobManager` for job lifecycle and logging
  - `worker.py` - `SyncWorker` for executing sync jobs in background threads
- **ETL pipeline**: `backend/etl/` - Data extraction, transformation, and loading
  - `pipeline.py` - `ETLPipeline` orchestrator
  - `stages/extract.py` - Batch extraction with watermark support
  - `stages/transform.py` - Field mapping and normalization
  - `stages/load.py` - SQLite storage with audit trails
- **Security**: `backend/security/` - Credential encryption
  - `credentials.py` - Fernet-based encryption for connector secrets
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
  - `MappingReview.tsx` - Schema mapping review and approval
  - `DataSources.tsx` - External data connector management
  - `SyncJobs.tsx` - Sync job monitoring with real-time updates
- **Components**: `frontend/src/components/`
  - `kirk/` - Kirk AI avatar, messages, thinking animation, follow-up chat
  - `analysis/` - FraudScoreGauge, ResultsDisplay
  - `layout/` - AppLayout, Sidebar (with mobile drawer), Header
  - `charts/` - SavingsChart, CategoryPieChart with accessibility support
  - `connectors/` - Data source connector components
    - `ConnectorCard.tsx` - Connector list item with status/actions
    - `ConnectorForm.tsx` - Multi-step wizard for creating connectors
    - `ConnectionTest.tsx` - Connection test modal with schema discovery
    - `ScheduleEditor.tsx` - Cron expression builder with presets
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
| POST | `/api/analyze/{job_id}?mapping_template=` | Run fraud analysis with optional field mapping |
| GET | `/api/results/{job_id}` | Get analysis results |
| GET | `/api/jobs?limit=100&offset=0` | List analyzed claims (paginated) |
| GET | `/api/stats` | Dashboard statistics |
| POST | `/api/search` | RAG policy document search |
| GET | `/api/mappings/templates` | List available field mapping templates |
| GET | `/api/mappings/schema` | Get canonical OMOP CDM schema definition |
| POST | `/api/mappings/preview` | Preview field mapping transformation |
| POST | `/api/mappings/semantic` | Find semantic matches for unknown fields (PubMedBERT) |
| POST | `/api/mappings/preview/semantic` | Preview mapping with semantic matching enabled |
| POST | `/api/mappings/rerank` | LLM rerank candidates with confidence scoring (Haiku) |
| POST | `/api/mappings/rerank/batch` | Batch rerank multiple field mappings |
| POST | `/api/mappings/smart` | Smart mapping: embeddings + LLM reranking pipeline |
| POST | `/api/mappings/save` | Save mapping with versioning |
| GET | `/api/mappings/stored` | List stored mappings (paginated, filter by status) |
| GET | `/api/mappings/stored/{mapping_id}` | Get mapping by ID |
| GET | `/api/mappings/stored/schema/{source_schema_id}` | Get mapping by source schema |
| POST | `/api/mappings/stored/{mapping_id}/approve` | Approve a pending mapping |
| POST | `/api/mappings/stored/{mapping_id}/reject` | Reject a pending mapping |
| GET | `/api/mappings/stored/{mapping_id}/audit` | Get audit trail for mapping |
| **Connectors** | | |
| GET | `/api/connectors` | List all connectors |
| POST | `/api/connectors` | Create connector |
| GET | `/api/connectors/{id}` | Get connector details |
| PUT | `/api/connectors/{id}` | Update connector |
| DELETE | `/api/connectors/{id}` | Delete connector |
| POST | `/api/connectors/{id}/test` | Test connection |
| POST | `/api/connectors/{id}/activate` | Enable scheduled sync |
| POST | `/api/connectors/{id}/deactivate` | Disable sync |
| GET | `/api/connectors/{id}/schema` | Discover source schema |
| POST | `/api/connectors/{id}/sync` | Trigger manual sync |
| POST | `/api/connectors/{id}/sample-analysis` | Run fraud analysis on sample claims |
| GET | `/api/connectors/types` | List available connector types |
| **Sync Jobs** | | |
| GET | `/api/sync-jobs` | List sync jobs |
| GET | `/api/sync-jobs/{id}` | Get job details |
| POST | `/api/sync-jobs/{id}/cancel` | Cancel running job |
| GET | `/api/sync-jobs/{id}/logs` | Get job logs |

### Data Flow

1. Claim submitted via POST `/api/upload` -> creates job
2. Analysis triggered via POST `/api/analyze/{job_id}` with claim data
3. **Field mapper** normalizes claim to OMOP CDM schema (alias matching + templates)
4. Rules engine evaluates normalized claim against datasets (NCCI, LCD, MPFS, OIG)
5. RAG searches relevant policy documents from ChromaDB
6. Claude generates explanation from rule hits + RAG context
7. Results stored in SQLite, returned as `AnalysisResult`

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
- sentence-transformers (PubMedBERT embeddings)
- scikit-learn (cosine similarity)

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
| `backend/mapping/omop_schema.py` | OMOP CDM canonical schema with aliases |
| `backend/mapping/mapper.py` | Field mapping transformation logic |
| `backend/mapping/embeddings.py` | PubMedBERT semantic field matching |
| `backend/mapping/reranker.py` | Claude Haiku LLM reranking for confidence scoring |
| `backend/mapping/persistence.py` | SQLite storage for mapping decisions with audit trail |
| `backend/mapping/templates/` | EDI 837P/I and CSV mapping templates |
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
| **Data Source Connectors** | |
| `backend/connectors/base.py` | BaseConnector abstract class |
| `backend/connectors/registry.py` | Connector type registry |
| `backend/connectors/database/base_db.py` | SQLAlchemy database connector base |
| `backend/connectors/database/postgresql.py` | PostgreSQL connector |
| `backend/connectors/database/mysql.py` | MySQL connector |
| `backend/connectors/file/base_file.py` | File connector base (S3, SFTP) |
| `backend/security/credentials.py` | Fernet credential encryption |
| **Scheduler & ETL** | |
| `backend/scheduler/scheduler.py` | APScheduler wrapper |
| `backend/scheduler/jobs.py` | Sync job lifecycle management |
| `backend/scheduler/worker.py` | Background job execution |
| `backend/etl/pipeline.py` | ETL orchestrator |
| `frontend/src/pages/DataSources.tsx` | Connector management UI |
| `frontend/src/pages/SyncJobs.tsx` | Job monitoring UI |
| `frontend/src/components/connectors/ConnectorForm.tsx` | Connector wizard |

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

## Field Mapping (OMOP CDM)

The system normalizes incoming claims from various formats to a canonical OMOP CDM schema.

### Supported Input Formats

| Format | Template | Description |
|--------|----------|-------------|
| EDI 837P | `edi_837p` | Professional claims (CMS-1500) |
| EDI 837I | `edi_837i` | Institutional claims (UB-04) |
| CSV | `csv` | Generic CSV field naming conventions |
| Custom | - | Alias-based automatic mapping |

### Canonical Field Examples

| Source Field | OMOP Canonical | Notes |
|--------------|---------------|-------|
| `patient_id`, `member_id`, `subscriber_id` | `person_id` | Auto-detected via aliases |
| `dos`, `date_of_service`, `service_date` | `visit_start_date` | Date normalization |
| `rendering_npi`, `billing_npi`, `provider_npi` | `npi` | Provider identifier |
| `cpt_code`, `hcpcs_code`, `procedure_code` | `procedure_source_value` | Procedure codes |

### Semantic Field Matching

For fields that don't match via aliases, the system uses **PubMedBERT embeddings** for semantic similarity:

| Model | Purpose |
|-------|---------|
| `pritamdeka/S-PubMedBert-MS-MARCO` | Default - Healthcare terminology |
| `dmis-lab/biobert-base-cased-v1.2` | Alternative biomedical model |
| `all-MiniLM-L6-v2` | Fast general-purpose fallback |

Configure via `EMBEDDING_MODEL` environment variable.

### Model Download & Caching Strategy

**First-time model loading:**
- PubMedBERT model (~420MB) downloads automatically on first use
- Download takes ~1-2 minutes depending on network speed
- Model is cached in `~/.cache/huggingface/hub/` for subsequent uses

**Production deployment:**
```bash
# Pre-load model on startup to avoid first-request latency
PRELOAD_EMBEDDINGS=true

# Model caching is in-memory (LRU cache with 1000 entries)
# Embeddings for canonical fields are pre-computed on initialization
```

**Performance considerations:**
- First request: ~2-3s (model loading + embedding computation)
- Subsequent requests: ~50-100ms (cached embeddings)
- Memory usage: ~420MB for PubMedBERT model in RAM

**Cost estimation (LLM Reranking):**
| Operation | Model | Cost per 1K fields |
|-----------|-------|-------------------|
| Single rerank | Haiku 4.5 | ~$0.05 |
| Batch rerank (20) | Haiku 4.5 | ~$0.02 |
| Smart mapping | Haiku 4.5 | ~$0.05 |

### LLM Reranking (Confidence Scoring)

The system uses **Claude Haiku 4.5** to rerank embedding candidates and provide confidence scores:

| Confidence | Action |
|------------|--------|
| ≥85% | Auto-accept mapping |
| 50-84% | Route to human review |
| <50% | Flag as low confidence |

Haiku is ~25x cheaper than Sonnet ($0.25/M vs $3/M input) while providing reliable structured selection.

**Configurable thresholds:**
```bash
MAPPING_HIGH_CONFIDENCE=85   # Auto-accept threshold (default: 85)
MAPPING_LOW_CONFIDENCE=50    # Low confidence threshold (default: 50)
RERANKER_MODEL=claude-haiku-4-5-20250514  # LLM model for reranking
```

**Rate limits:**
| Endpoint | Limit | Reason |
|----------|-------|--------|
| `/api/mappings/rerank` | 10/minute | Single LLM call |
| `/api/mappings/rerank/batch` | 5/minute | Multiple LLM calls (max 20/batch) |
| `/api/mappings/smart` | 10/minute | Embedding + LLM pipeline |

### API Usage

```bash
# Analyze with default alias mapping
POST /api/analyze/{job_id}

# Analyze with EDI 837P template
POST /api/analyze/{job_id}?mapping_template=edi_837p

# Preview mapping transformation
POST /api/mappings/preview
{
  "sample_data": {"patient_id": "P123", "dos": "2024-01-15"},
  "template": "csv"
}

# Find semantic matches for unknown fields
POST /api/mappings/semantic
{
  "fields": ["PatientMRN", "MemberBirthDate", "RenderingProviderNPI"],
  "top_k": 5,
  "min_similarity": 0.5
}

# Preview with semantic matching enabled
POST /api/mappings/preview/semantic
{
  "sample_data": {"PatientMRN": "P123", "MemberBirthDate": "1980-05-15"},
  "semantic_threshold": 0.7
}

# LLM reranking for confidence scoring
POST /api/mappings/rerank
{
  "source_field": "PatientMRN",
  "candidates": [{"field": "person_id", "score": 0.85}],
  "sample_values": ["MRN-123", "MRN-456"]
}

# Smart mapping: Embeddings + LLM reranking pipeline
POST /api/mappings/smart
{
  "source_fields": ["PatientMRN", "MemberDOB"],
  "top_k": 5,
  "min_similarity": 0.5
}

# Get canonical schema
GET /api/mappings/schema
```

### Python Usage

```python
from mapping import normalize_claim, normalize_claim_with_review, FieldMapper

# Basic normalization (alias matching only)
normalized = normalize_claim(raw_claim)

# With semantic matching for unknown fields
normalized = normalize_claim(raw_claim, use_semantic_matching=True, semantic_threshold=0.7)

# Get semantic matches for review
normalized, semantic_matches = normalize_claim_with_review(raw_claim)
# semantic_matches: {"PatientMRN": ("person_id", 0.92), ...}

# Advanced usage with FieldMapper
mapper = FieldMapper(
    custom_mapping={"MyCustomField": "person_id"},
    use_semantic_matching=True,
    semantic_threshold=0.8
)
result = mapper.transform(raw_claim)
matches = mapper.get_semantic_matches()  # For human review
```

### Mapping Persistence & Versioning

Field mappings can be saved for audit trails and continuous improvement:

```bash
# Save a new mapping
POST /api/mappings/save
{
  "source_schema_id": "payer_format_a",
  "field_mappings": [
    {"source_field": "MemberID", "target_field": "person_id", "confidence": 0.95, "method": "alias"}
  ],
  "created_by": "user@example.com"
}

# List pending mappings
GET /api/mappings/stored?status=pending&limit=50

# Approve a mapping
POST /api/mappings/stored/{mapping_id}/approve
{"approved_by": "reviewer@example.com"}

# Get audit trail
GET /api/mappings/stored/{mapping_id}/audit
```

```python
from mapping import get_mapping_store, MappingStatus

store = get_mapping_store()

# Save mapping
mapping = store.save_mapping(
    source_schema_id="payer_format_a",
    field_mappings=[{"source_field": "MemberID", "target_field": "person_id", "confidence": 0.95}],
    created_by="system"
)

# Approve and track
store.approve_mapping(mapping.id, approved_by="reviewer@example.com")

# Get audit history
audit = store.get_audit_log(mapping.id)
```

## Data Source Connectors

The system supports external data source integration for claims, eligibility, provider, and reference data.

### Supported Connector Types

| Type | Subtype | Description |
|------|---------|-------------|
| Database | `postgresql` | PostgreSQL with SSL support |
| Database | `mysql` | MySQL/MariaDB |
| File | `s3` | AWS S3 bucket |
| File | `sftp` | SFTP server |

### Data Types

| Type | Description | Example Sources |
|------|-------------|-----------------|
| `claims` | Healthcare claims (837P/I) | Claims database, EDI files |
| `eligibility` | Member eligibility | Eligibility system |
| `providers` | Provider data | NPI registry, credentialing |
| `reference` | Reference data | NCCI edits, LCD policies |

### Connector Configuration

```bash
# Create a PostgreSQL connector
POST /api/connectors
{
  "name": "Claims Database",
  "connector_type": "database",
  "subtype": "postgresql",
  "data_type": "claims",
  "connection_config": {
    "host": "db.example.com",
    "port": 5432,
    "database": "claims_db",
    "username": "reader",
    "password": "secret",  # Encrypted at rest
    "ssl_mode": "require",
    "table": "claims",
    "watermark_column": "updated_at"
  },
  "sync_schedule": "0 */6 * * *",  # Every 6 hours
  "sync_mode": "incremental"
}

# Test connection
POST /api/connectors/{id}/test

# Discover schema
GET /api/connectors/{id}/schema

# Trigger manual sync
POST /api/connectors/{id}/sync?sync_mode=incremental
```

### Sync Job Monitoring

```bash
# List recent jobs
GET /api/sync-jobs?limit=50

# Get job status (auto-polls while running)
GET /api/sync-jobs/{id}
# Returns: {status: "running", processed_records: 5000, total_records: 10000}

# Cancel running job
POST /api/sync-jobs/{id}/cancel

# View job logs
GET /api/sync-jobs/{id}/logs
```

### Cron Schedule Format

| Expression | Description |
|------------|-------------|
| `0 * * * *` | Every hour at minute 0 |
| `0 */6 * * *` | Every 6 hours |
| `0 0 * * *` | Daily at midnight |
| `0 6 * * 1` | Weekly on Monday at 6am |
| `0 0 1 * *` | Monthly on the 1st |

### Environment Variables

```bash
# Credential encryption key (required for production)
CREDENTIAL_ENCRYPTION_KEY=<fernet-key>

# Generate key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Python Usage

```python
from connectors import get_connector_registry
from connectors.database import PostgreSQLConnector

# Get available connector types
registry = get_connector_registry()
types = registry.list_types()

# Create and test a connector
connector = PostgreSQLConnector(
    connector_id="test-1",
    name="Test Connection",
    config={
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "username": "user",
        "password": "pass"
    }
)
result = connector.test_connection()
if result.success:
    schema = connector.discover_schema()
    print(f"Found {len(schema.tables)} tables")

# Extract data
connector.connect()
for batch in connector.extract(sync_mode=SyncMode.FULL):
    process_records(batch)
connector.disconnect()
```
