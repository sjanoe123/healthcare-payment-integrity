"""Tests for audit logging routes."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def client(test_db):
    """Create test client with patched database."""
    with patch.dict(os.environ, {"DB_PATH": test_db}):
        # Reset initialization flag for each test
        import routes.audit as audit_module

        audit_module._audit_table_initialized = False

        from app import app

        with TestClient(app) as client:
            yield client


class TestAuditLogEvent:
    """Tests for log_audit_event function."""

    def test_logs_basic_event(self, test_db):
        """Test logging a basic audit event."""
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            from routes.audit import get_db, init_audit_table, log_audit_event

            conn = get_db()
            init_audit_table(conn)

            audit_id = log_audit_event(
                conn,
                action="test.action",
                user_id="user123",
                user_email="test@example.com",
                resource_type="claim",
                resource_id="claim456",
                details={"key": "value"},
                status="success",
            )

            assert audit_id is not None
            assert len(audit_id) == 36  # UUID format

            # Verify it was saved
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_logs WHERE id = ?", (audit_id,))
            row = cursor.fetchone()

            assert row is not None
            assert row[2] == "test.action"
            assert row[3] == "user123"
            assert row[4] == "test@example.com"
            assert row[5] == "claim"
            assert row[6] == "claim456"
            assert json.loads(row[7]) == {"key": "value"}
            assert row[10] == "success"

            conn.close()

    def test_logs_error_event(self, test_db):
        """Test logging an error event."""
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            import routes.audit as audit_module

            # Reset the flag to ensure table gets created
            audit_module._audit_table_initialized = False

            from routes.audit import get_db, init_audit_table, log_audit_event

            conn = get_db()
            init_audit_table(conn)  # Must init table first

            audit_id = log_audit_event(
                conn,
                action="test.error",
                status="error",
                error_message="Something went wrong",
            )

            cursor = conn.cursor()
            cursor.execute("SELECT status, error_message FROM audit_logs WHERE id = ?", (audit_id,))
            row = cursor.fetchone()

            assert row[0] == "error"
            assert row[1] == "Something went wrong"

            conn.close()


class TestListAuditLogs:
    """Tests for list_audit_logs endpoint."""

    def test_returns_empty_list_initially(self, client):
        """Test that endpoint returns empty list when no logs exist."""
        response = client.get("/api/audit")
        assert response.status_code == 200

        data = response.json()
        assert data["entries"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_returns_logs_with_pagination(self, client, test_db):
        """Test pagination of audit logs."""
        # Add some logs directly
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            from routes.audit import get_db, init_audit_table, log_audit_event

            conn = get_db()
            init_audit_table(conn)

            for i in range(25):
                log_audit_event(conn, action=f"test.action{i}", status="success")

            conn.close()

        # Test first page
        response = client.get("/api/audit?limit=10&offset=0")
        assert response.status_code == 200

        data = response.json()
        assert len(data["entries"]) == 10
        assert data["total"] == 25
        assert data["limit"] == 10
        assert data["offset"] == 0

        # Test second page
        response = client.get("/api/audit?limit=10&offset=10")
        data = response.json()
        assert len(data["entries"]) == 10
        assert data["offset"] == 10

    def test_filters_by_action(self, client, test_db):
        """Test filtering by action type."""
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            from routes.audit import get_db, init_audit_table, log_audit_event

            conn = get_db()
            init_audit_table(conn)

            log_audit_event(conn, action="claim.upload", status="success")
            log_audit_event(conn, action="claim.analyze", status="success")
            log_audit_event(conn, action="connector.create", status="success")

            conn.close()

        response = client.get("/api/audit?action=claim.upload")
        data = response.json()

        assert data["total"] == 1
        assert data["entries"][0]["action"] == "claim.upload"
        assert data["filters_applied"]["action"] == "claim.upload"

    def test_filters_by_status(self, client, test_db):
        """Test filtering by status."""
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            from routes.audit import get_db, init_audit_table, log_audit_event

            conn = get_db()
            init_audit_table(conn)

            log_audit_event(conn, action="test.success", status="success")
            log_audit_event(conn, action="test.error", status="error")
            log_audit_event(conn, action="test.success2", status="success")

            conn.close()

        response = client.get("/api/audit?status=error")
        data = response.json()

        assert data["total"] == 1
        assert data["entries"][0]["status"] == "error"


class TestAuditStats:
    """Tests for get_audit_stats endpoint."""

    def test_returns_zero_stats_initially(self, client):
        """Test stats with no logs."""
        response = client.get("/api/audit/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total_entries"] == 0
        assert data["entries_by_action"] == {}
        assert data["entries_by_status"] == {}

    def test_returns_correct_stats(self, client, test_db):
        """Test stats calculation."""
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            from routes.audit import get_db, init_audit_table, log_audit_event

            conn = get_db()
            init_audit_table(conn)

            # Add varied logs
            log_audit_event(conn, action="claim.upload", user_id="user1", status="success")
            log_audit_event(conn, action="claim.upload", user_id="user1", status="success")
            log_audit_event(conn, action="claim.analyze", user_id="user2", status="error")

            conn.close()

        response = client.get("/api/audit/stats")
        data = response.json()

        assert data["total_entries"] == 3
        assert data["entries_by_action"]["claim.upload"] == 2
        assert data["entries_by_action"]["claim.analyze"] == 1
        assert data["entries_by_status"]["success"] == 2
        assert data["entries_by_status"]["error"] == 1
        assert "user1" in data["entries_by_user"]
        assert "user2" in data["entries_by_user"]


class TestExportAuditLogs:
    """Tests for export_audit_logs endpoint."""

    def test_exports_csv(self, client, test_db):
        """Test CSV export."""
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            from routes.audit import get_db, init_audit_table, log_audit_event

            conn = get_db()
            init_audit_table(conn)

            log_audit_event(conn, action="test.export", status="success")
            conn.close()

        response = client.get("/api/audit/export?format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert ".csv" in response.headers["content-disposition"]

        # Check CSV content
        content = response.text
        assert "ID,Timestamp,Action" in content
        assert "test.export" in content

    def test_exports_json(self, client, test_db):
        """Test JSON export."""
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            from routes.audit import get_db, init_audit_table, log_audit_event

            conn = get_db()
            init_audit_table(conn)

            log_audit_event(conn, action="test.json.export", status="success")
            conn.close()

        response = client.get("/api/audit/export?format=json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        data = response.json()
        assert "audit_logs" in data
        assert "exported_at" in data
        assert len(data["audit_logs"]) >= 1

    def test_respects_limit(self, client, test_db):
        """Test export row limit."""
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            from routes.audit import get_db, init_audit_table, log_audit_event

            conn = get_db()
            init_audit_table(conn)

            for i in range(10):
                log_audit_event(conn, action=f"test.bulk{i}", status="success")
            conn.close()

        response = client.get("/api/audit/export?format=json&limit=5")
        data = response.json()

        assert len(data["audit_logs"]) == 5


class TestListAuditActions:
    """Tests for list_audit_actions endpoint."""

    def test_returns_all_actions(self, client):
        """Test that all action types are returned."""
        response = client.get("/api/audit/actions")
        assert response.status_code == 200

        data = response.json()
        assert "actions" in data
        assert "categories" in data
        # Check that we have some actions
        assert len(data["actions"]) > 0
        # Check for common actions (from AuditAction enum)
        assert any("claim" in action for action in data["actions"])

    def test_returns_categorized_actions(self, client):
        """Test action categorization."""
        response = client.get("/api/audit/actions")
        data = response.json()

        categories = data["categories"]
        # Verify category structure exists
        assert isinstance(categories, dict)
        # At minimum claim category should exist
        assert "claim" in categories
        # Claim category should have claim-prefixed actions
        if categories["claim"]:
            assert all(action.startswith("claim.") for action in categories["claim"])


class TestInitAuditTable:
    """Tests for thread-safe table initialization."""

    def test_initialization_is_idempotent(self, test_db):
        """Test that multiple calls to init_audit_table are safe."""
        with patch.dict(os.environ, {"DB_PATH": test_db}):
            import routes.audit as audit_module

            audit_module._audit_table_initialized = False

            from routes.audit import get_db, init_audit_table

            conn = get_db()

            # Call multiple times
            init_audit_table(conn)
            init_audit_table(conn)
            init_audit_table(conn)

            # Verify table exists and has correct structure
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(audit_logs)")
            columns = [row[1] for row in cursor.fetchall()]

            assert "id" in columns
            assert "timestamp" in columns
            assert "action" in columns
            assert "user_id" in columns
            assert "status" in columns

            conn.close()
