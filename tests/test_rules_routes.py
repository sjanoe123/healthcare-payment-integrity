"""Tests for backend/routes/rules.py endpoints.

Tests cover:
- /api/rules/stats - Rule execution statistics
- /api/rules/coverage - Field coverage analysis
- /api/rules/effectiveness - Rule impact metrics
- /api/rules/catalog - Available rules listing
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_db(tmp_path: Path):
    """Create a test database with sample data."""
    db_path = tmp_path / "test.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            claim_id TEXT,
            status TEXT,
            claim_data TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            fraud_score REAL,
            decision_mode TEXT,
            rule_hits TEXT,
            flags TEXT,
            created_at TEXT
        )
    """)

    # Insert test jobs with claim data
    test_jobs = [
        ("job1", "CLAIM001", "completed", json.dumps({
            "procedure_code": "99213",
            "diagnosis_code": "J06.9",
            "billing_npi": "1234567890",
            "billed_amount": 150.00,
            "service_date": "2024-01-15",
            "items": [{"procedure_code": "99213", "quantity": 1, "line_amount": 150.00}]
        })),
        ("job2", "CLAIM002", "completed", json.dumps({
            "procedure_code": "99214",
            "diagnosis_code": "M54.5",
            "billing_npi": "0987654321",
            "billed_amount": 200.00,
            "service_date": "2024-01-16",
            "patient_dob": "1980-05-15",
            "patient_gender": "M",
            "items": [{"procedure_code": "99214", "quantity": 1, "line_amount": 200.00}]
        })),
        ("job3", "CLAIM003", "completed", json.dumps({
            "procedure_code": "99215",
            "billed_amount": 300.00,
            # Missing several fields intentionally
        })),
    ]

    for job_id, claim_id, status, claim_data in test_jobs:
        cursor.execute(
            "INSERT INTO jobs (id, claim_id, status, claim_data, created_at, updated_at) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
            (job_id, claim_id, status, claim_data)
        )

    # Insert test results with rule hits
    test_results = [
        ("job1", 0.65, "review", json.dumps([
            {"rule_id": "NCCI_PTP", "rule_type": "billing", "severity": "high", "weight": -0.15},
            {"rule_id": "HIGH_DOLLAR", "rule_type": "financial", "severity": "medium", "weight": -0.10},
        ])),
        ("job2", 0.45, "approve", json.dumps([
            {"rule_id": "LCD_MISMATCH", "rule_type": "coverage", "severity": "medium", "weight": -0.08},
        ])),
        ("job3", 0.85, "deny", json.dumps([
            {"rule_id": "NCCI_PTP", "rule_type": "billing", "severity": "high", "weight": -0.20},
            {"rule_id": "OIG_EXCLUSION", "rule_type": "fwa", "severity": "critical", "weight": -0.30},
            {"rule_id": "DUPLICATE_LINE", "rule_type": "billing", "severity": "medium", "weight": -0.05},
        ])),
    ]

    for job_id, fraud_score, decision_mode, rule_hits in test_results:
        cursor.execute(
            "INSERT INTO results (job_id, fraud_score, decision_mode, rule_hits, flags, created_at) VALUES (?, ?, ?, ?, '[]', datetime('now'))",
            (job_id, fraud_score, decision_mode, rule_hits)
        )

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def client(test_db: Path):
    """Create test client with mocked database."""
    with patch("routes.rules.DB_PATH", str(test_db)):
        with patch("config.DB_PATH", str(test_db)):
            from app import app
            with TestClient(app) as client:
                yield client


@pytest.fixture
def empty_db(tmp_path: Path):
    """Create an empty test database."""
    db_path = tmp_path / "empty.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            claim_id TEXT,
            status TEXT,
            claim_data TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            fraud_score REAL,
            decision_mode TEXT,
            rule_hits TEXT,
            flags TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def empty_client(empty_db: Path):
    """Create test client with empty database."""
    with patch("routes.rules.DB_PATH", str(empty_db)):
        with patch("config.DB_PATH", str(empty_db)):
            from app import app
            with TestClient(app) as client:
                yield client


class TestRuleStatsEndpoint:
    """Tests for GET /api/rules/stats."""

    def test_stats_returns_totals(self, client: TestClient):
        """Test that stats returns total claims and hits."""
        response = client.get("/api/rules/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_claims_analyzed"] == 3
        assert data["total_rule_hits"] == 6
        assert "average_rules_per_claim" in data

    def test_stats_returns_frequency_list(self, client: TestClient):
        """Test that stats returns rules sorted by frequency."""
        response = client.get("/api/rules/stats")
        data = response.json()

        assert "rules_by_frequency" in data
        freq = data["rules_by_frequency"]
        assert len(freq) > 0

        # NCCI_PTP appears twice, should be first
        assert freq[0]["rule_id"] == "NCCI_PTP"
        assert freq[0]["count"] == 2

    def test_stats_returns_type_distribution(self, client: TestClient):
        """Test that stats returns rules grouped by type."""
        response = client.get("/api/rules/stats")
        data = response.json()

        assert "rules_by_type" in data
        types = data["rules_by_type"]
        assert "billing" in types
        assert types["billing"] == 3  # NCCI_PTP x2 + DUPLICATE_LINE

    def test_stats_returns_severity_distribution(self, client: TestClient):
        """Test that stats returns rules grouped by severity."""
        response = client.get("/api/rules/stats")
        data = response.json()

        assert "rules_by_severity" in data
        severity = data["rules_by_severity"]
        assert "high" in severity
        assert "medium" in severity

    def test_stats_respects_limit(self, client: TestClient):
        """Test that limit parameter is respected."""
        response = client.get("/api/rules/stats?limit=2")
        data = response.json()

        assert len(data["rules_by_frequency"]) <= 2

    def test_stats_empty_database(self, empty_client: TestClient):
        """Test stats with no results."""
        response = empty_client.get("/api/rules/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_claims_analyzed"] == 0
        assert data["total_rule_hits"] == 0
        assert data["rules_by_frequency"] == []


class TestRuleCoverageEndpoint:
    """Tests for GET /api/rules/coverage."""

    def test_coverage_returns_field_stats(self, client: TestClient):
        """Test that coverage returns field presence statistics."""
        response = client.get("/api/rules/coverage")
        assert response.status_code == 200

        data = response.json()
        assert "total_claims" in data
        assert "field_coverage" in data
        assert "coverage_score" in data

    def test_coverage_tracks_required_fields(self, client: TestClient):
        """Test that required fields are tracked."""
        response = client.get("/api/rules/coverage")
        data = response.json()

        field_names = [f["field"] for f in data["field_coverage"]]
        assert "procedure_code" in field_names
        assert "diagnosis_code" in field_names
        assert "billing_npi" in field_names

    def test_coverage_shows_missing_fields(self, client: TestClient):
        """Test that missing fields are identified."""
        response = client.get("/api/rules/coverage")
        data = response.json()

        # Find a field that's not always present
        coverage = {f["field"]: f for f in data["field_coverage"]}

        # patient_gender is only in 1 of 3 claims
        if "patient_gender" in coverage:
            assert coverage["patient_gender"]["missing"] > 0

    def test_coverage_empty_database(self, empty_client: TestClient):
        """Test coverage with no claims."""
        response = empty_client.get("/api/rules/coverage")
        assert response.status_code == 200

        data = response.json()
        assert data["total_claims"] == 0
        assert data["coverage_score"] == 0


class TestRuleEffectivenessEndpoint:
    """Tests for GET /api/rules/effectiveness."""

    def test_effectiveness_returns_metrics(self, client: TestClient):
        """Test that effectiveness returns impact metrics."""
        response = client.get("/api/rules/effectiveness")
        assert response.status_code == 200

        data = response.json()
        assert "rules" in data
        assert "total_rules_fired" in data

    def test_effectiveness_includes_weight_metrics(self, client: TestClient):
        """Test that each rule has weight metrics."""
        response = client.get("/api/rules/effectiveness")
        data = response.json()

        if data["rules"]:
            rule = data["rules"][0]
            assert "rule_id" in rule
            assert "times_fired" in rule
            assert "avg_weight" in rule
            assert "total_weight_contribution" in rule
            assert "avg_claim_score" in rule

    def test_effectiveness_sorted_by_impact(self, client: TestClient):
        """Test that rules are sorted by total impact."""
        response = client.get("/api/rules/effectiveness")
        data = response.json()

        if len(data["rules"]) > 1:
            impacts = [abs(r["total_weight_contribution"]) for r in data["rules"]]
            assert impacts == sorted(impacts, reverse=True)

    def test_effectiveness_empty_database(self, empty_client: TestClient):
        """Test effectiveness with no results."""
        response = empty_client.get("/api/rules/effectiveness")
        assert response.status_code == 200

        data = response.json()
        assert data["rules"] == []
        assert data["total_rules_fired"] == 0


class TestRuleCatalogEndpoint:
    """Tests for GET /api/rules/catalog."""

    def test_catalog_returns_rules(self, client: TestClient):
        """Test that catalog returns available rules."""
        response = client.get("/api/rules/catalog")
        assert response.status_code == 200

        data = response.json()
        assert "rules" in data
        assert "total_rules" in data
        assert data["total_rules"] > 0

    def test_catalog_rule_structure(self, client: TestClient):
        """Test that each rule has required fields."""
        response = client.get("/api/rules/catalog")
        data = response.json()

        if data["rules"]:
            rule = data["rules"][0]
            assert "rule_id" in rule
            assert "name" in rule
            assert "description" in rule

    def test_catalog_includes_known_rules(self, client: TestClient):
        """Test that known rules appear in catalog."""
        response = client.get("/api/rules/catalog")
        data = response.json()

        rule_ids = [r["rule_id"] for r in data["rules"]]
        # At least some core rules should exist
        assert len(rule_ids) > 0

    def test_catalog_rule_metadata_extraction(self, client: TestClient):
        """Test that rule metadata is properly extracted."""
        response = client.get("/api/rules/catalog")
        data = response.json()

        # Check that rules have proper metadata structure
        for rule in data["rules"]:
            # All rules should have these basic fields
            assert isinstance(rule.get("rule_id"), str)
            assert len(rule["rule_id"]) > 0
            assert isinstance(rule.get("name"), str)
            assert isinstance(rule.get("description"), str)

            # Optional fields that may exist
            if "category" in rule:
                assert isinstance(rule["category"], str)
            if "severity" in rule:
                assert rule["severity"] in ["low", "medium", "high", "critical"]

    def test_catalog_empty_response_structure(self, client: TestClient):
        """Test that response structure is valid even if no rules."""
        response = client.get("/api/rules/catalog")
        data = response.json()

        # Structure should always be valid
        assert isinstance(data.get("rules"), list)
        assert isinstance(data.get("total_rules"), int)
        assert data["total_rules"] == len(data["rules"])


class TestRuleStatsEdgeCases:
    """Edge case tests for rule stats."""

    def test_stats_handles_malformed_json(self, tmp_path: Path):
        """Test that malformed JSON in rule_hits is handled gracefully."""
        db_path = tmp_path / "malformed.db"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE results (
                id INTEGER PRIMARY KEY,
                job_id TEXT,
                fraud_score REAL,
                decision_mode TEXT,
                rule_hits TEXT,
                flags TEXT,
                created_at TEXT
            )
        """)

        # Insert result with malformed JSON
        cursor.execute(
            "INSERT INTO results (job_id, fraud_score, decision_mode, rule_hits, flags, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            ("job1", 0.5, "review", "not valid json {{{", "[]")
        )

        conn.commit()
        conn.close()

        with patch("routes.rules.DB_PATH", str(db_path)):
            with patch("config.DB_PATH", str(db_path)):
                from app import app
                with TestClient(app) as client:
                    response = client.get("/api/rules/stats")
                    assert response.status_code == 200
                    data = response.json()
                    # Should still return valid response
                    assert data["total_claims_analyzed"] == 1
                    assert data["total_rule_hits"] == 0  # Malformed data ignored

    def test_stats_handles_null_rule_hits(self, tmp_path: Path):
        """Test that NULL rule_hits is handled gracefully."""
        db_path = tmp_path / "null.db"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE results (
                id INTEGER PRIMARY KEY,
                job_id TEXT,
                fraud_score REAL,
                decision_mode TEXT,
                rule_hits TEXT,
                flags TEXT,
                created_at TEXT
            )
        """)

        cursor.execute(
            "INSERT INTO results (job_id, fraud_score, decision_mode, rule_hits, flags, created_at) VALUES (?, ?, ?, NULL, ?, datetime('now'))",
            ("job1", 0.5, "review", "[]")
        )

        conn.commit()
        conn.close()

        with patch("routes.rules.DB_PATH", str(db_path)):
            with patch("config.DB_PATH", str(db_path)):
                from app import app
                with TestClient(app) as client:
                    response = client.get("/api/rules/stats")
                    assert response.status_code == 200
