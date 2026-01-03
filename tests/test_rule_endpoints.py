"""Tests for the rule coverage API endpoints."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile

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


@pytest.fixture
def db_with_results():
    """Create a database with sample results for testing."""
    db_path = os.environ["DB_PATH"]
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert sample results
    sample_results = [
        (
            "job-1",
            "CLM-001",
            0.75,
            "review",
            json.dumps([
                {"rule_id": "NCCI_PTP", "severity": "high", "rule_type": "ncci", "weight": 0.15},
                {"rule_id": "FORMAT_MISSING_FIELD", "severity": "medium", "rule_type": "format", "weight": 0.05},
            ]),
            json.dumps(["NCCI_PTP"]),
            json.dumps([]),
            json.dumps([]),
            150.0,
        ),
        (
            "job-2",
            "CLM-002",
            0.50,
            "approve",
            json.dumps([
                {"rule_id": "NCCI_PTP", "severity": "high", "rule_type": "ncci", "weight": 0.15},
            ]),
            json.dumps(["NCCI_PTP"]),
            json.dumps([]),
            json.dumps([]),
            75.0,
        ),
        (
            "job-3",
            "CLM-003",
            0.85,
            "deny",
            json.dumps([
                {"rule_id": "OIG_EXCLUSION", "severity": "critical", "rule_type": "fwa", "weight": 0.25},
                {"rule_id": "FWA_WATCH", "severity": "high", "rule_type": "fwa", "weight": 0.10},
            ]),
            json.dumps([]),
            json.dumps([]),
            json.dumps(["OIG_EXCLUSION"]),
            500.0,
        ),
    ]

    for result in sample_results:
        cursor.execute(
            """
            INSERT OR REPLACE INTO results
            (job_id, claim_id, fraud_score, decision_mode, rule_hits,
             ncci_flags, coverage_flags, provider_flags, roi_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            result,
        )

    conn.commit()
    conn.close()

    yield

    # Cleanup
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM results WHERE job_id IN ('job-1', 'job-2', 'job-3')")
    conn.commit()
    conn.close()


class TestRuleStatsEndpoint:
    """Tests for GET /api/rules/stats."""

    def test_returns_stats_structure(self, client: TestClient):
        """Test that the endpoint returns the expected structure."""
        response = client.get("/api/rules/stats")
        assert response.status_code == 200
        data = response.json()
        # Check structure matches routes/rules.py
        assert "total_claims_analyzed" in data
        assert "total_rule_hits" in data
        assert "rules_by_frequency" in data

    def test_aggregates_rule_hits(self, client: TestClient, db_with_results):
        """Test that rule hits are aggregated correctly."""
        response = client.get("/api/rules/stats")
        assert response.status_code == 200
        data = response.json()

        assert data["total_claims_analyzed"] >= 3
        assert data["total_rule_hits"] >= 5

    def test_includes_rules_by_type(self, client: TestClient, db_with_results):
        """Test that rules are grouped by type."""
        response = client.get("/api/rules/stats")
        data = response.json()

        # Should have ncci and fwa types
        assert "rules_by_type" in data


class TestRuleCatalogEndpoint:
    """Tests for GET /api/rules/catalog."""

    def test_returns_rule_catalog(self, client: TestClient):
        """Test that the catalog endpoint returns available rules."""
        response = client.get("/api/rules/catalog")
        assert response.status_code == 200
        data = response.json()

        assert "rules" in data
        assert "total_rules" in data
        # Note: total_rules may be 0 in test environment if rules aren't registered
        assert isinstance(data["total_rules"], int)
        assert isinstance(data["rules"], list)


class TestRuleEffectivenessEndpoint:
    """Tests for GET /api/rules/effectiveness."""

    def test_returns_effectiveness_structure(self, client: TestClient):
        """Test that the endpoint returns the expected structure."""
        response = client.get("/api/rules/effectiveness")
        assert response.status_code == 200
        data = response.json()

        assert "rules" in data
        assert "total_rules_fired" in data

    def test_calculates_effectiveness_metrics(self, client: TestClient, db_with_results):
        """Test that effectiveness metrics are calculated."""
        response = client.get("/api/rules/effectiveness")
        data = response.json()

        if data["rules"]:
            rule = data["rules"][0]
            assert "rule_id" in rule
            assert "times_fired" in rule
            assert "avg_weight" in rule
            assert "avg_claim_score" in rule
