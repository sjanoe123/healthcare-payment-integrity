.PHONY: help install run seed test test-integration lint lint-fix docker-build docker-up docker-down clean data-all data-leie data-ncci data-mpfs data-lcd

help:
	@echo "Healthcare Payment Integrity Prototype"
	@echo ""
	@echo "Usage:"
	@echo "  make install     Install Python dependencies locally"
	@echo "  make run         Run the backend locally (no Docker)"
	@echo "  make seed        Seed ChromaDB with policy documents (24 docs)"
	@echo "  make test        Run unit tests with pytest"
	@echo "  make test-integration  Run integration tests against running server"
	@echo "  make lint        Run linting checks (ruff)"
	@echo "  make lint-fix    Auto-fix linting issues"
	@echo ""
	@echo "Data Commands (Phase 2 - Real CMS Data):"
	@echo "  make data-all    Download all CMS reference data (~10 min)"
	@echo "  make data-ncci   Download NCCI PTP/MUE from CMS (29K+ pairs, 8K+ MUE)"
	@echo "  make data-mpfs   Download MPFS fee schedule from CMS (10K+ codes)"
	@echo "  make data-lcd    Download LCD coverage data from CMS (79+ policies)"
	@echo "  make data-leie   Load OIG exclusion list (8K+ NPIs)"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-up     Start with Docker Compose"
	@echo "  make docker-down   Stop Docker Compose"
	@echo ""
	@echo "  make clean       Clean up data files"

install:
	pip install -r backend/requirements.txt

run:
	cd backend && PYTHONPATH=. uvicorn app:app --reload --host 0.0.0.0 --port 8080

seed:
	cd backend && PYTHONPATH=. python ../scripts/seed_chromadb.py

test:
	PYTHONPATH=backend pytest tests/ -v

test-integration:
	python scripts/test_analysis.py

lint:
	ruff check backend/ scripts/
	ruff format --check backend/ scripts/

lint-fix:
	ruff check backend/ scripts/ --fix
	ruff format backend/ scripts/

# Data generation targets
data-leie:
	python scripts/load_leie.py

data-ncci:
	python scripts/download_ncci.py

data-mpfs:
	python scripts/download_mpfs.py

data-lcd:
	python scripts/download_lcd.py

data-all: data-ncci data-mpfs data-lcd data-leie seed
	@echo ""
	@echo "=============================================="
	@echo "All CMS reference data downloaded successfully!"
	@echo "=============================================="
	@echo ""
	@echo "Phase 2 Data Summary:"
	@echo "  - NCCI PTP Edits: data/ncci_ptp.json (29K+ code pairs)"
	@echo "  - NCCI MUE Limits: data/ncci_mue.json (8K+ codes)"
	@echo "  - MPFS Rates: data/mpfs.json (10K+ procedures)"
	@echo "  - LCD Coverage: data/lcd.json (79+ policies)"
	@echo "  - OIG Exclusions: data/oig_exclusions.json (8K+ NPIs)"
	@echo "  - ChromaDB RAG: data/chroma/ (24 policy documents)"
	@echo ""
	@echo "Run 'make run' to start the backend with this data."

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d
	@echo "Backend running at http://localhost:8080"
	@echo "API docs at http://localhost:8080/docs"

docker-down:
	docker-compose down

clean:
	rm -rf data/chroma data/prototype.db
	@echo "Cleaned up data files"
