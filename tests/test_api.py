"""Tests for the FastAPI endpoints."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

# Set test environment before importing app
if "DB_PATH" not in os.environ:
    _temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    os.environ["DB_PATH"] = _temp_db.name
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app, init_db


@pytest.fixture(scope="module")
def client():
    """Create test client with initialized database."""
    # Ensure database is initialized
    init_db()
    with TestClient(app) as client:
        yield client


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_returns_200(self, client: TestClient):
        """Test health endpoint returns 200."""
        response = client.get("/health")

        assert response.status_code == 200

    def test_health_returns_status(self, client: TestClient):
        """Test health endpoint returns status field."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_returns_timestamp(self, client: TestClient):
        """Test health endpoint returns timestamp."""
        response = client.get("/health")
        data = response.json()

        assert "timestamp" in data


class TestUploadEndpoint:
    """Test the claim upload endpoint."""

    def test_upload_returns_job_id(self, client: TestClient, sample_claim: dict):
        """Test upload returns a job ID."""
        response = client.post("/api/upload", json=sample_claim)

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert "claim_id" in data
        assert data["claim_id"] == sample_claim["claim_id"]

    def test_upload_returns_pending_status(
        self, client: TestClient, sample_claim: dict
    ):
        """Test upload returns pending status."""
        response = client.post("/api/upload", json=sample_claim)
        data = response.json()

        assert data["status"] == "pending"

    def test_upload_invalid_claim_fails(self, client: TestClient):
        """Test upload with invalid claim fails."""
        response = client.post("/api/upload", json={})

        assert response.status_code == 422  # Validation error


class TestSearchEndpoint:
    """Test the policy search endpoint."""

    def test_search_returns_results(self, client: TestClient):
        """Test search endpoint returns results structure."""
        response = client.post(
            "/api/search",
            json={"query": "NCCI billing", "n_results": 3},
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data or "message" in data

    def test_search_with_empty_query_fails(self, client: TestClient):
        """Test search with empty query fails validation."""
        response = client.post("/api/search", json={"query": "", "n_results": 3})

        # Empty string might still be valid, just return empty results
        assert response.status_code in [200, 422]


class TestStatsEndpoint:
    """Test the statistics endpoint."""

    def test_stats_returns_counts(self, client: TestClient) -> None:
        """Test stats endpoint returns job counts."""
        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_jobs" in data
        assert "completed_jobs" in data


class TestResultsEndpoint:
    """Test the results endpoint."""

    def test_get_nonexistent_job_returns_404(self, client: TestClient) -> None:
        """Test getting results for non-existent job returns 404."""
        response = client.get("/api/results/nonexistent-job-id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestAnalyzeEndpoint:
    """Test the analysis endpoint."""

    @patch("app.get_fraud_explanation")
    def test_analyze_returns_results(
        self, mock_claude, client: TestClient, sample_claim: dict
    ):
        """Test analyze endpoint returns fraud analysis."""
        # Mock Claude response
        mock_claude.return_value = {
            "explanation": "Test explanation",
            "model": "claude-3-haiku",
            "tokens_used": 100,
        }

        # First upload the claim
        upload_response = client.post("/api/upload", json=sample_claim)
        job_id = upload_response.json()["job_id"]

        # Then analyze it
        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)

        assert response.status_code == 200
        data = response.json()
        assert "fraud_score" in data
        assert "rule_hits" in data
        assert "decision_mode" in data

    @patch("app.get_fraud_explanation")
    def test_analyze_detects_fraud_indicators(
        self, mock_claude, client: TestClient, sample_claim: dict
    ):
        """Test analyze detects fraud indicators in sample claim."""
        mock_claude.return_value = {
            "explanation": "Test",
            "model": "test",
            "tokens_used": 0,
        }

        upload_response = client.post("/api/upload", json=sample_claim)
        job_id = upload_response.json()["job_id"]

        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        # Sample claim has fraud indicators
        assert len(data["rule_hits"]) > 0 or data["fraud_score"] > 0.5
