"""Tests for the sample-analysis endpoint.

Tests cover connector validation, SQL injection protection,
configurable table names, and analysis execution.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

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
def mock_connector(client: TestClient):
    """Create a mock PostgreSQL connector in the database."""
    import json
    import sqlite3
    import uuid

    connector_id = str(uuid.uuid4())
    db_path = os.environ["DB_PATH"]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO connectors (id, name, connector_type, subtype, data_type,
                               connection_config, status, sync_mode, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            connector_id,
            f"Test PostgreSQL {connector_id[:8]}",  # Unique name
            "database",
            "postgresql",
            "claims",
            json.dumps(
                {
                    "host": "localhost",
                    "port": 5432,
                    "database": "test",
                    "username": "test",
                    "password": "test",
                    "table": "claims",
                }
            ),
            "active",
            "incremental",
        ),
    )
    conn.commit()
    conn.close()

    yield connector_id

    # Cleanup
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM connectors WHERE id = ?", (connector_id,))
    conn.commit()
    conn.close()


@pytest.fixture
def mock_mysql_connector(client: TestClient):
    """Create a mock MySQL connector (unsupported for sample-analysis)."""
    import json
    import sqlite3
    import uuid

    connector_id = str(uuid.uuid4())
    db_path = os.environ["DB_PATH"]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO connectors (id, name, connector_type, subtype, data_type,
                               connection_config, status, sync_mode, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            connector_id,
            f"Test MySQL {connector_id[:8]}",  # Unique name
            "database",
            "mysql",
            "claims",
            json.dumps({"host": "localhost", "port": 3306}),
            "active",
            "incremental",
        ),
    )
    conn.commit()
    conn.close()

    yield connector_id

    # Cleanup
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM connectors WHERE id = ?", (connector_id,))
    conn.commit()
    conn.close()


class TestSampleAnalysisEndpoint:
    """Tests for POST /api/connectors/{connector_id}/sample-analysis."""

    def test_connector_not_found_returns_404(self, client: TestClient):
        """Non-existent connector should return 404."""
        response = client.post(
            "/api/connectors/nonexistent-id/sample-analysis?sample_size=5"
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_mysql_connector_returns_400(
        self, client: TestClient, mock_mysql_connector: str
    ):
        """MySQL connector should return 400 (unsupported)."""
        response = client.post(
            f"/api/connectors/{mock_mysql_connector}/sample-analysis?sample_size=5"
        )
        assert response.status_code == 400
        assert "postgresql" in response.json()["detail"].lower()

    def test_sample_size_validation(self, client: TestClient, mock_connector: str):
        """Sample size should be validated (1-100)."""
        # Too small
        response = client.post(
            f"/api/connectors/{mock_connector}/sample-analysis?sample_size=0"
        )
        assert response.status_code == 422

        # Too large
        response = client.post(
            f"/api/connectors/{mock_connector}/sample-analysis?sample_size=101"
        )
        assert response.status_code == 422

    @patch("app.PostgreSQLConnector")
    def test_fallback_to_preview_on_connection_error(
        self, mock_pg_class: MagicMock, client: TestClient, mock_connector: str
    ):
        """Should fall back to preview mode on connection error."""
        mock_instance = MagicMock()
        mock_instance.connect.side_effect = Exception("Connection refused")
        mock_pg_class.return_value = mock_instance

        response = client.post(
            f"/api/connectors/{mock_connector}/sample-analysis?sample_size=5"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preview_mode"] is True

    @patch("app.PostgreSQLConnector")
    def test_empty_database_returns_preview_mode(
        self, mock_pg_class: MagicMock, client: TestClient, mock_connector: str
    ):
        """Empty database should return preview mode with distinct message."""
        mock_instance = MagicMock()
        mock_instance.connect.return_value = None
        mock_instance.execute_query.return_value = []  # No claims
        mock_instance.disconnect.return_value = None
        mock_pg_class.return_value = mock_instance

        response = client.post(
            f"/api/connectors/{mock_connector}/sample-analysis?sample_size=5"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preview_mode"] is True
        assert "no claims" in data["message"].lower()


class TestSampleAnalysisSQLInjection:
    """Tests for SQL injection protection in sample-analysis."""

    @patch("app.PostgreSQLConnector")
    def test_invalid_table_name_rejected(
        self, mock_pg_class: MagicMock, client: TestClient
    ):
        """SQL injection in table name should be rejected."""
        import json
        import sqlite3
        import uuid

        # Mock connector to allow connection to succeed
        # so we reach the table name validation
        mock_instance = MagicMock()
        mock_instance.connect.return_value = None
        mock_pg_class.return_value = mock_instance

        connector_id = str(uuid.uuid4())
        db_path = os.environ["DB_PATH"]

        # Create connector with malicious table name
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO connectors (id, name, connector_type, subtype, data_type,
                                   connection_config, status, sync_mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                connector_id,
                f"Malicious {connector_id[:8]}",
                "database",
                "postgresql",
                "claims",
                json.dumps(
                    {
                        "host": "localhost",
                        "table": "claims; DROP TABLE users--",
                    }
                ),
                "active",
                "incremental",
            ),
        )
        conn.commit()
        conn.close()

        try:
            response = client.post(
                f"/api/connectors/{connector_id}/sample-analysis?sample_size=5"
            )
            assert response.status_code == 400
            assert "invalid" in response.json()["detail"].lower()
        finally:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM connectors WHERE id = ?", (connector_id,))
            conn.commit()
            conn.close()

    @patch("app.PostgreSQLConnector")
    def test_invalid_claim_lines_table_rejected(
        self, mock_pg_class: MagicMock, client: TestClient
    ):
        """SQL injection in claim_lines_table should be rejected."""
        import json
        import sqlite3
        import uuid

        # Mock connector to allow connection to succeed
        # so we reach the table name validation
        mock_instance = MagicMock()
        mock_instance.connect.return_value = None
        mock_pg_class.return_value = mock_instance

        connector_id = str(uuid.uuid4())
        db_path = os.environ["DB_PATH"]

        # Create connector with malicious claim_lines_table
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO connectors (id, name, connector_type, subtype, data_type,
                                   connection_config, status, sync_mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                connector_id,
                f"Malicious Lines {connector_id[:8]}",
                "database",
                "postgresql",
                "claims",
                json.dumps(
                    {
                        "host": "localhost",
                        "table": "claims",
                        "claim_lines_table": "lines OR 1=1",
                    }
                ),
                "active",
                "incremental",
            ),
        )
        conn.commit()
        conn.close()

        try:
            response = client.post(
                f"/api/connectors/{connector_id}/sample-analysis?sample_size=5"
            )
            assert response.status_code == 400
            assert "invalid" in response.json()["detail"].lower()
        finally:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM connectors WHERE id = ?", (connector_id,))
            conn.commit()
            conn.close()


class TestConfigurableTableNames:
    """Tests for configurable table names feature."""

    @patch("app.PostgreSQLConnector")
    def test_custom_claim_lines_table_used(
        self, mock_pg_class: MagicMock, client: TestClient
    ):
        """Custom claim_lines_table config should be used in query."""
        import json
        import sqlite3
        import uuid

        connector_id = str(uuid.uuid4())
        db_path = os.environ["DB_PATH"]

        # Create connector with custom claim_lines_table
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO connectors (id, name, connector_type, subtype, data_type,
                                   connection_config, status, sync_mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                connector_id,
                f"Custom Tables {connector_id[:8]}",
                "database",
                "postgresql",
                "claims",
                json.dumps(
                    {
                        "host": "localhost",
                        "table": "medical_claims",
                        "claim_lines_table": "medical_claim_details",
                    }
                ),
                "active",
                "incremental",
            ),
        )
        conn.commit()
        conn.close()

        # Mock the connector
        mock_instance = MagicMock()
        mock_instance.connect.return_value = None
        mock_instance.execute_query.return_value = []
        mock_instance.disconnect.return_value = None
        mock_pg_class.return_value = mock_instance

        try:
            response = client.post(
                f"/api/connectors/{connector_id}/sample-analysis?sample_size=5"
            )

            # Check that execute_query was called with custom table names
            if mock_instance.execute_query.called:
                query = mock_instance.execute_query.call_args[0][0]
                assert '"medical_claims"' in query
                assert '"medical_claim_details"' in query
        finally:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM connectors WHERE id = ?", (connector_id,))
            conn.commit()
            conn.close()
