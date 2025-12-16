.PHONY: help install run seed test docker-build docker-up docker-down clean data-all data-leie data-ncci data-mpfs

help:
	@echo "Healthcare Payment Integrity Prototype"
	@echo ""
	@echo "Usage:"
	@echo "  make install     Install Python dependencies locally"
	@echo "  make run         Run the backend locally (no Docker)"
	@echo "  make seed        Seed ChromaDB with policy documents (24 docs)"
	@echo "  make test        Run the test script against running server"
	@echo ""
	@echo "Data Commands:"
	@echo "  make data-all    Generate all reference data"
	@echo "  make data-leie   Load OIG exclusion list (8K+ NPIs)"
	@echo "  make data-ncci   Generate NCCI PTP/MUE data"
	@echo "  make data-mpfs   Generate MPFS fee schedule data"
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
	python scripts/test_analysis.py

# Data generation targets
data-leie:
	python scripts/load_leie.py

data-ncci:
	python scripts/download_ncci.py

data-mpfs:
	python scripts/download_mpfs.py

data-all: data-leie data-ncci data-mpfs seed
	@echo ""
	@echo "All reference data generated successfully!"
	@echo "  - OIG Exclusions: data/oig_exclusions.json"
	@echo "  - NCCI PTP/MUE: data/ncci_ptp.json, data/ncci_mue.json"
	@echo "  - MPFS Rates: data/mpfs.json"
	@echo "  - ChromaDB: data/chroma/ (24 policy documents)"

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
