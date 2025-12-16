# Healthcare Payment Integrity Prototype

A lightweight, local-first prototype for healthcare fraud detection using:
- **FastAPI** backend with 13 fraud detection rules
- **ChromaDB** for RAG (Retrieval Augmented Generation)
- **Claude API** (Anthropic) for intelligent explanations
- **SQLite** for local persistence

## Quick Start

### Prerequisites
- Python 3.12+
- (Optional) Docker and Docker Compose
- Anthropic API key for Claude (optional but recommended)

### Option 1: Run Locally (Recommended for Development)

```bash
# Install dependencies
make install

# Set your Anthropic API key (optional)
export ANTHROPIC_API_KEY="your-key-here"

# Seed ChromaDB with sample policy documents
make seed

# Run the backend
make run
```

The API will be available at:
- **API**: http://localhost:8080
- **Docs**: http://localhost:8080/docs

### Option 2: Run with Docker

```bash
# Create .env file with your API key
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# Build and start
make docker-up

# Stop
make docker-down
```

## Testing

With the server running:

```bash
make test
```

This runs a comprehensive test that:
1. Checks the health endpoint
2. Tests RAG search
3. Submits a sample claim with fraud indicators
4. Displays the analysis results

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with RAG document count |
| `/api/upload` | POST | Submit a claim for analysis |
| `/api/analyze/{job_id}` | POST | Run fraud analysis on a claim |
| `/api/results/{job_id}` | GET | Get analysis results |
| `/api/search` | POST | Search policy documents (RAG) |
| `/api/stats` | GET | Get prototype statistics |

## Sample Claim

```json
{
  "claim_id": "TEST-001",
  "billed_amount": 15000.00,
  "diagnosis_codes": ["J06.9", "M54.5"],
  "items": [
    {
      "procedure_code": "99214",
      "diagnosis_code": "J06.9",
      "quantity": 1,
      "line_amount": 150.00
    }
  ],
  "provider": {
    "npi": "1234567890",
    "specialty": "internal medicine"
  },
  "member": {
    "age": 45,
    "gender": "F"
  }
}
```

## Fraud Detection Rules

The prototype includes 13 baseline rules:

1. **HIGH_DOLLAR** - High dollar amount detection
2. **REIMB_OUTLIER** - Reimbursement outliers vs benchmarks
3. **NCCI_PTP** - NCCI Procedure-to-Procedure edit violations
4. **NCCI_MUE** - NCCI Medically Unlikely Edit violations
5. **LCD_MISMATCH** - LCD coverage diagnosis mismatches
6. **LCD_AGE_CONFLICT** - Age outside LCD guidance
7. **LCD_GENDER_CONFLICT** - Gender outside LCD guidance
8. **LCD_EXPERIMENTAL** - Experimental/investigational procedures
9. **GLOBAL_SURGERY_NO_MODIFIER** - Missing global surgery modifiers
10. **OIG_EXCLUSION** - Provider on OIG exclusion list
11. **FWA_WATCH** - Provider on fraud watchlist
12. **UTIL_OUTLIER** - Utilization outliers
13. **DUPLICATE_LINE** - Duplicate procedure lines

## Cost

- **Infrastructure**: $0 (runs locally)
- **Claude API**: ~$0.25 per 1M input tokens with Haiku
- **Typical claim analysis**: < $0.001

## Directory Structure

```
prototype/
├── backend/
│   ├── app.py              # FastAPI application
│   ├── claude_client.py    # Anthropic API client
│   ├── rules/              # 13 fraud detection rules
│   ├── rag/                # ChromaDB integration
│   └── Dockerfile
├── scripts/
│   ├── seed_chromadb.py    # Seed RAG with policies
│   └── test_analysis.py    # Test script
├── data/                   # Local data (git ignored)
├── docker-compose.yaml
└── Makefile
```
