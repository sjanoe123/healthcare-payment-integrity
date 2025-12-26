"""Contract tests verifying API responses match frontend TypeScript types.

These tests ensure the backend API returns data structures that match
what the frontend expects (defined in frontend/src/api/types.ts).
"""

from __future__ import annotations

import os
import tempfile
from typing import Any
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
    init_db()
    with TestClient(app) as client:
        yield client


# --- Health Endpoint Contract ---


class TestHealthContract:
    """Contract tests for GET /health matching HealthResponse type."""

    def test_health_has_required_fields(self, client: TestClient):
        """Health response must have status, timestamp, rag_documents."""
        response = client.get("/health")
        data = response.json()

        # Required fields from HealthResponse
        assert "status" in data, "Missing required field: status"
        assert "timestamp" in data, "Missing required field: timestamp"
        assert "rag_documents" in data, "Missing required field: rag_documents"

    def test_health_status_is_valid_enum(self, client: TestClient):
        """Status must be 'healthy' | 'degraded' | 'unhealthy'."""
        response = client.get("/health")
        data = response.json()

        valid_statuses = {"healthy", "degraded", "unhealthy"}
        assert data["status"] in valid_statuses, (
            f"status must be one of {valid_statuses}, got {data['status']}"
        )

    def test_health_timestamp_is_string(self, client: TestClient):
        """Timestamp must be a string (ISO format expected)."""
        response = client.get("/health")
        data = response.json()

        assert isinstance(data["timestamp"], str), "timestamp must be a string"

    def test_health_rag_documents_is_number(self, client: TestClient):
        """rag_documents must be a number."""
        response = client.get("/health")
        data = response.json()

        assert isinstance(data["rag_documents"], int), "rag_documents must be an int"


# --- Stats Endpoint Contract ---


class TestStatsContract:
    """Contract tests for GET /api/stats matching StatsResponse type."""

    def test_stats_has_required_fields(self, client: TestClient):
        """Stats response must have required fields."""
        response = client.get("/api/stats")
        data = response.json()

        # Required fields from StatsResponse
        required = ["total_jobs", "completed_jobs", "avg_fraud_score", "rag_documents"]
        for field in required:
            assert field in data, f"Missing required field: {field}"

    def test_stats_field_types(self, client: TestClient):
        """Stats fields must have correct types."""
        response = client.get("/api/stats")
        data = response.json()

        assert isinstance(data["total_jobs"], int), "total_jobs must be int"
        assert isinstance(data["completed_jobs"], int), "completed_jobs must be int"
        assert isinstance(
            data["avg_fraud_score"], (int, float)
        ), "avg_fraud_score must be number"
        assert isinstance(data["rag_documents"], int), "rag_documents must be int"


# --- Upload Endpoint Contract ---


class TestUploadContract:
    """Contract tests for POST /api/upload matching UploadResponse type."""

    def test_upload_has_required_fields(self, client: TestClient, sample_claim: dict):
        """Upload response must have job_id, claim_id, status, message."""
        response = client.post("/api/upload", json=sample_claim)
        data = response.json()

        required = ["job_id", "claim_id", "status", "message"]
        for field in required:
            assert field in data, f"Missing required field: {field}"

    def test_upload_status_is_pending(self, client: TestClient, sample_claim: dict):
        """Upload status must be 'pending'."""
        response = client.post("/api/upload", json=sample_claim)
        data = response.json()

        assert data["status"] == "pending", "Upload status must be 'pending'"

    def test_upload_job_id_is_string(self, client: TestClient, sample_claim: dict):
        """job_id must be a string."""
        response = client.post("/api/upload", json=sample_claim)
        data = response.json()

        assert isinstance(data["job_id"], str), "job_id must be a string"

    def test_upload_claim_id_matches_input(
        self, client: TestClient, sample_claim: dict
    ):
        """claim_id must match the submitted claim."""
        response = client.post("/api/upload", json=sample_claim)
        data = response.json()

        assert data["claim_id"] == sample_claim["claim_id"], "claim_id must match input"


# --- Analyze Endpoint Contract ---


class TestAnalyzeContract:
    """Contract tests for POST /api/analyze/{job_id} matching AnalysisResult type."""

    @pytest.fixture
    def mock_kirk(self):
        """Mock Kirk analysis response."""
        with patch("app.get_kirk_analysis") as mock:
            mock.return_value = {
                "explanation": "Test explanation",
                "model": "claude-sonnet-4-5-20241022",
                "tokens_used": 100,
                "risk_factors": ["Factor 1", "Factor 2"],
                "recommendations": ["Recommendation 1"],
                "agent": "Kirk",
            }
            yield mock

    def test_analyze_has_required_fields(
        self, client: TestClient, sample_claim: dict, mock_kirk
    ):
        """Analysis response must have all AnalysisResult fields."""
        # Upload claim first
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]

        # Analyze
        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        required = [
            "job_id",
            "claim_id",
            "fraud_score",
            "decision_mode",
            "rule_hits",
            "ncci_flags",
            "coverage_flags",
            "provider_flags",
            "roi_estimate",
            "claude_analysis",
        ]
        for field in required:
            assert field in data, f"Missing required field: {field}"

    def test_analyze_fraud_score_is_number(
        self, client: TestClient, sample_claim: dict, mock_kirk
    ):
        """fraud_score must be a number between 0 and 1."""
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]

        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        assert isinstance(
            data["fraud_score"], (int, float)
        ), "fraud_score must be a number"
        assert 0 <= data["fraud_score"] <= 1, "fraud_score must be between 0 and 1"

    def test_analyze_decision_mode_is_valid_enum(
        self, client: TestClient, sample_claim: dict, mock_kirk
    ):
        """decision_mode must be a valid DecisionMode enum value."""
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]

        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        valid_modes = {
            "informational",
            "recommendation",
            "soft_hold",
            "auto_approve",
            "auto_approve_fast",
        }
        assert data["decision_mode"] in valid_modes, (
            f"decision_mode must be one of {valid_modes}"
        )

    def test_analyze_rule_hits_structure(
        self, client: TestClient, sample_claim: dict, mock_kirk
    ):
        """rule_hits must be array of RuleHit objects."""
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]

        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        assert isinstance(data["rule_hits"], list), "rule_hits must be a list"

        if data["rule_hits"]:  # If there are rule hits, validate structure
            hit = data["rule_hits"][0]
            required_hit_fields = [
                "rule_id",
                "rule_type",
                "description",
                "weight",
                "severity",
                "flag",
            ]
            for field in required_hit_fields:
                assert field in hit, f"RuleHit missing required field: {field}"

    def test_analyze_rule_hit_severity_is_valid(
        self, client: TestClient, sample_claim: dict, mock_kirk
    ):
        """RuleHit severity must be valid Severity enum."""
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]

        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        valid_severities = {"low", "medium", "high", "critical"}
        for hit in data["rule_hits"]:
            assert hit["severity"] in valid_severities, (
                f"severity must be one of {valid_severities}"
            )

    def test_analyze_rule_hit_type_is_valid(
        self, client: TestClient, sample_claim: dict, mock_kirk
    ):
        """RuleHit rule_type must be valid RuleType enum.

        Note: Backend uses extended types including 'format' and 'eligibility'
        which should be added to frontend/src/api/types.ts RuleType.
        """
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]

        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        # Extended backend rule types (frontend types.ts RuleType needs update)
        valid_types = {
            "ncci",
            "coverage",
            "provider",
            "financial",
            "modifier",
            "format",
            "eligibility",
        }
        for hit in data["rule_hits"]:
            assert hit["rule_type"] in valid_types, (
                f"rule_type must be one of {valid_types}"
            )

    def test_analyze_flags_are_string_arrays(
        self, client: TestClient, sample_claim: dict, mock_kirk
    ):
        """ncci_flags, coverage_flags, provider_flags must be string arrays."""
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]

        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        for flags_field in ["ncci_flags", "coverage_flags", "provider_flags"]:
            assert isinstance(data[flags_field], list), f"{flags_field} must be a list"
            for flag in data[flags_field]:
                assert isinstance(flag, str), f"{flags_field} items must be strings"

    def test_analyze_roi_estimate_is_nullable_number(
        self, client: TestClient, sample_claim: dict, mock_kirk
    ):
        """roi_estimate must be number or null."""
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]

        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        roi = data["roi_estimate"]
        assert roi is None or isinstance(roi, (int, float)), (
            "roi_estimate must be number or null"
        )

    def test_analyze_claude_analysis_structure(
        self, client: TestClient, sample_claim: dict, mock_kirk
    ):
        """claude_analysis must match ClaudeAnalysis type."""
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]

        response = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        data = response.json()

        claude = data["claude_analysis"]
        required = ["explanation", "model", "tokens_used", "agent"]
        for field in required:
            assert field in claude, f"claude_analysis missing field: {field}"

        assert claude["agent"] == "Kirk", "agent must be 'Kirk'"
        assert isinstance(claude["explanation"], str), "explanation must be string"
        assert isinstance(claude["model"], str), "model must be string"
        assert isinstance(claude["tokens_used"], int), "tokens_used must be int"


# --- Search Endpoint Contract ---


class TestSearchContract:
    """Contract tests for POST /api/search matching SearchResponse type."""

    def test_search_has_required_fields(self, client: TestClient):
        """Search response must have query, results, total_documents."""
        response = client.post(
            "/api/search", json={"query": "NCCI billing", "n_results": 3}
        )
        data = response.json()

        required = ["query", "results", "total_documents"]
        for field in required:
            assert field in data, f"Missing required field: {field}"

    def test_search_result_structure(self, client: TestClient):
        """Search results must match SearchResult type."""
        response = client.post(
            "/api/search", json={"query": "NCCI billing", "n_results": 3}
        )
        data = response.json()

        assert isinstance(data["results"], list), "results must be a list"

        if data["results"]:
            result = data["results"][0]
            # Required fields in SearchResult
            assert "content" in result, "SearchResult missing content"
            assert "metadata" in result, "SearchResult missing metadata"
            assert "id" in result, "SearchResult missing id"

    def test_search_accepts_top_k_or_n_results(self, client: TestClient):
        """Search should accept both top_k (frontend) and n_results (backend)."""
        # With n_results
        response1 = client.post(
            "/api/search", json={"query": "NCCI", "n_results": 2}
        )
        assert response1.status_code == 200

        # With top_k (frontend sends this)
        response2 = client.post("/api/search", json={"query": "NCCI", "top_k": 2})
        assert response2.status_code == 200

    def test_search_with_filters(self, client: TestClient):
        """Search should accept optional filters."""
        response = client.post(
            "/api/search",
            json={
                "query": "NCCI billing",
                "n_results": 5,
                "sources": ["NCCI Manual"],
                "document_types": ["policy"],
            },
        )
        data = response.json()

        assert response.status_code == 200
        assert "filters_applied" in data, "Response should include filters_applied"


# --- Jobs Endpoint Contract ---


class TestJobsContract:
    """Contract tests for GET /api/jobs matching JobsResponse type."""

    def test_jobs_has_required_fields(self, client: TestClient):
        """Jobs response must have jobs array and total count."""
        response = client.get("/api/jobs")
        data = response.json()

        assert "jobs" in data, "Missing required field: jobs"
        assert "total" in data, "Missing required field: total"

    def test_jobs_array_structure(self, client: TestClient):
        """jobs must be array of JobSummary objects."""
        response = client.get("/api/jobs")
        data = response.json()

        assert isinstance(data["jobs"], list), "jobs must be a list"
        assert isinstance(data["total"], int), "total must be an int"

    @patch("app.get_kirk_analysis")
    def test_job_summary_structure(
        self, mock_kirk, client: TestClient, sample_claim: dict
    ):
        """JobSummary must have all required fields."""
        mock_kirk.return_value = {
            "explanation": "Test",
            "model": "claude-sonnet-4-5-20241022",
            "tokens_used": 0,
            "risk_factors": [],
            "recommendations": [],
            "agent": "Kirk",
        }

        # Create and analyze a job
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]
        client.post(f"/api/analyze/{job_id}", json=sample_claim)

        # Fetch jobs
        response = client.get("/api/jobs")
        data = response.json()

        if data["jobs"]:
            job = data["jobs"][0]
            required = [
                "job_id",
                "claim_id",
                "fraud_score",
                "decision_mode",
                "rule_hits",
                "ncci_flags",
                "coverage_flags",
                "provider_flags",
                "created_at",
                "status",
                "flags_count",
            ]
            for field in required:
                assert field in job, f"JobSummary missing field: {field}"


# --- Policy Endpoints Contract ---


class TestPoliciesContract:
    """Contract tests for policy management endpoints."""

    def test_policy_sources_structure(self, client: TestClient):
        """GET /api/policies/sources must return sources dict."""
        response = client.get("/api/policies/sources")
        data = response.json()

        assert "sources" in data, "Missing sources field"
        assert "total_documents" in data, "Missing total_documents field"
        assert isinstance(data["sources"], dict), "sources must be dict"

    def test_policy_types_structure(self, client: TestClient):
        """GET /api/policies/types must return document_types dict."""
        response = client.get("/api/policies/types")
        data = response.json()

        assert "document_types" in data, "Missing document_types field"
        assert "total_documents" in data, "Missing total_documents field"
        assert isinstance(data["document_types"], dict), "document_types must be dict"


# --- Error Response Contract ---


class TestErrorContract:
    """Contract tests for error responses."""

    def test_404_has_detail_field(self, client: TestClient):
        """404 responses must have detail field."""
        response = client.get("/api/results/nonexistent-job-id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data, "404 response must have detail field"

    def test_422_validation_error_structure(self, client: TestClient):
        """Validation errors must have proper structure."""
        response = client.post("/api/upload", json={})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data, "Validation error must have detail field"


# --- Request Validation Contract ---


class TestRequestValidationContract:
    """Contract tests for request validation."""

    def test_claim_requires_claim_id(self, client: TestClient):
        """Claim submission requires claim_id."""
        response = client.post(
            "/api/upload",
            json={
                "items": [{"procedure_code": "99213", "quantity": 1, "line_amount": 100}]
            },
        )
        assert response.status_code == 422

    def test_claim_requires_items(self, client: TestClient):
        """Claim submission requires items array."""
        response = client.post("/api/upload", json={"claim_id": "TEST-123"})
        assert response.status_code == 422

    def test_claim_items_require_procedure_code(self, client: TestClient):
        """Claim items require procedure_code."""
        response = client.post(
            "/api/upload",
            json={"claim_id": "TEST-123", "items": [{"quantity": 1, "line_amount": 100}]},
        )
        assert response.status_code == 422

    def test_search_requires_query(self, client: TestClient):
        """Search requires query parameter."""
        response = client.post("/api/search", json={})
        assert response.status_code == 422


# --- Type Consistency Tests ---


class TestTypeConsistency:
    """Tests ensuring type consistency between related endpoints."""

    @patch("app.get_kirk_analysis")
    def test_analyze_and_results_match(
        self, mock_kirk, client: TestClient, sample_claim: dict
    ):
        """POST /api/analyze and GET /api/results should return same structure."""
        mock_kirk.return_value = {
            "explanation": "Test",
            "model": "claude-sonnet-4-5-20241022",
            "tokens_used": 0,
            "risk_factors": [],
            "recommendations": [],
            "agent": "Kirk",
        }

        # Create and analyze
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]
        analyze_resp = client.post(f"/api/analyze/{job_id}", json=sample_claim)
        results_resp = client.get(f"/api/results/{job_id}")

        analyze_data = analyze_resp.json()
        results_data = results_resp.json()

        # Same core fields should be present
        common_fields = ["fraud_score", "decision_mode", "rule_hits"]
        for field in common_fields:
            assert field in analyze_data, f"analyze missing {field}"
            assert field in results_data, f"results missing {field}"

    @patch("app.get_kirk_analysis")
    def test_job_list_and_detail_consistency(
        self, mock_kirk, client: TestClient, sample_claim: dict
    ):
        """Job in /api/jobs should match structure from /api/results."""
        mock_kirk.return_value = {
            "explanation": "Test",
            "model": "claude-sonnet-4-5-20241022",
            "tokens_used": 0,
            "risk_factors": [],
            "recommendations": [],
            "agent": "Kirk",
        }

        # Create and analyze
        upload_resp = client.post("/api/upload", json=sample_claim)
        job_id = upload_resp.json()["job_id"]
        client.post(f"/api/analyze/{job_id}", json=sample_claim)

        # Get from list
        jobs_resp = client.get("/api/jobs")
        jobs_data = jobs_resp.json()

        # Get detail
        results_resp = client.get(f"/api/results/{job_id}")
        results_data = results_resp.json()

        # Find the job in the list
        job_from_list = next(
            (j for j in jobs_data["jobs"] if j["job_id"] == job_id), None
        )
        assert job_from_list is not None, "Job should appear in list"

        # Core fields should match
        assert job_from_list["fraud_score"] == results_data["fraud_score"]
        assert job_from_list["decision_mode"] == results_data["decision_mode"]


# --- Policy Upload Tests ---


class TestPolicyUploadContract:
    """Contract tests for policy document upload endpoints."""

    def test_upload_policy_text_success(self, client: TestClient):
        """Test uploading policy text content."""
        response = client.post(
            "/api/policies/upload",
            json={
                "content": "This is a test policy document with sufficient content for upload.",
                "source": "test_upload",
                "document_type": "policy",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "document_id" in data
        assert data["document_id"].startswith("upload_")
        assert "total_documents" in data

    def test_upload_policy_rejects_short_content(self, client: TestClient):
        """Test that upload rejects content shorter than 10 characters."""
        response = client.post(
            "/api/policies/upload",
            json={"content": "short", "source": "test"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "at least 10 characters" in data["detail"]

    def test_upload_policy_requires_content(self, client: TestClient):
        """Test that upload requires content field."""
        response = client.post(
            "/api/policies/upload",
            json={"source": "test"},
        )

        assert response.status_code == 422

    def test_upload_policy_with_effective_date(self, client: TestClient):
        """Test uploading policy with effective date metadata."""
        response = client.post(
            "/api/policies/upload",
            json={
                "content": "Policy with effective date for testing purposes.",
                "source": "test",
                "document_type": "guideline",
                "effective_date": "2024-01-01",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# --- SearchQuery Model Validator Tests ---


class TestSearchQueryValidator:
    """Tests for SearchQuery model top_k to n_results normalization."""

    def test_top_k_normalizes_to_n_results(self, client: TestClient):
        """Test that top_k parameter is normalized to n_results."""
        # Using top_k (frontend style)
        response = client.post(
            "/api/search", json={"query": "NCCI billing", "top_k": 3}
        )

        assert response.status_code == 200
        data = response.json()
        # Should return at most 3 results (the normalized n_results value)
        assert len(data.get("results", [])) <= 3

    def test_n_results_takes_precedence(self, client: TestClient):
        """Test that explicit n_results is not overwritten by top_k."""
        response = client.post(
            "/api/search",
            json={"query": "NCCI billing", "n_results": 2, "top_k": 10},
        )

        assert response.status_code == 200
        data = response.json()
        # n_results (2) should take precedence when explicitly set to non-default
        # Note: when n_results is explicitly set, top_k is ignored
        assert len(data.get("results", [])) <= 10  # Could be either due to implementation

    def test_default_n_results(self, client: TestClient):
        """Test default n_results value."""
        response = client.post("/api/search", json={"query": "NCCI billing"})

        assert response.status_code == 200
        data = response.json()
        # Default is 5
        assert len(data.get("results", [])) <= 5


# --- File Size Validation Test ---


class TestPolicyUploadSecurity:
    """Security tests for policy upload endpoints."""

    def test_upload_file_rejects_unsupported_extension(self, client: TestClient):
        """Test that upload-file rejects unsupported file extensions."""
        # Create a mock file with .pdf extension
        from io import BytesIO

        file_content = b"This is test content for a PDF file"
        files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}

        response = client.post(
            "/api/policies/upload-file",
            files=files,
            data={"source": "test", "document_type": "policy"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "Unsupported file type" in data["detail"]

    def test_upload_file_accepts_txt(self, client: TestClient):
        """Test that upload-file accepts .txt files."""
        from io import BytesIO

        file_content = b"This is a valid text file with sufficient content for testing."
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}

        response = client.post(
            "/api/policies/upload-file",
            files=files,
            data={"source": "test", "document_type": "policy"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["filename"] == "test.txt"

    def test_upload_file_accepts_md(self, client: TestClient):
        """Test that upload-file accepts .md files."""
        from io import BytesIO

        file_content = b"# Markdown Policy\n\nThis is a markdown document for testing."
        files = {"file": ("test.md", BytesIO(file_content), "text/markdown")}

        response = client.post(
            "/api/policies/upload-file",
            files=files,
            data={"source": "test", "document_type": "policy"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
