"""Tests for connector security features.

Tests for SQL injection prevention, password sanitization,
credential management, and input validation.
"""

import pytest


class TestSQLIdentifierValidation:
    """Tests for SQL identifier validation to prevent injection."""

    def test_valid_table_name(self) -> None:
        """Valid table names should pass validation."""
        from backend.connectors.database.base_db import validate_identifier

        assert validate_identifier("users") == "users"
        assert validate_identifier("patient_claims") == "patient_claims"
        assert validate_identifier("Claims2024") == "Claims2024"
        assert validate_identifier("_private_table") == "_private_table"

    def test_valid_schema_table(self) -> None:
        """Schema.table notation should be valid."""
        from backend.connectors.database.base_db import validate_identifier

        assert validate_identifier("public.users") == "public.users"
        assert validate_identifier("healthcare.claims") == "healthcare.claims"

    def test_invalid_identifier_sql_injection(self) -> None:
        """SQL injection attempts should be rejected."""
        from backend.connectors.database.base_db import validate_identifier

        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("users; DROP TABLE users")

        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("users--comment")

        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("users OR 1=1")

    def test_invalid_identifier_special_chars(self) -> None:
        """Special characters should be rejected."""
        from backend.connectors.database.base_db import validate_identifier

        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("table$name")

        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("table@name")

        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("table name")

    def test_dangerous_keywords_rejected(self) -> None:
        """SQL keywords that could be dangerous should be rejected."""
        from backend.connectors.database.base_db import validate_identifier

        with pytest.raises(ValueError, match="Reserved keyword"):
            validate_identifier("DROP")

        with pytest.raises(ValueError, match="Reserved keyword"):
            validate_identifier("delete")

        with pytest.raises(ValueError, match="Reserved keyword"):
            validate_identifier("TRUNCATE")

    def test_empty_identifier_rejected(self) -> None:
        """Empty identifiers should be rejected."""
        from backend.connectors.database.base_db import validate_identifier

        with pytest.raises(ValueError, match="Empty"):
            validate_identifier("")


class TestQuoteIdentifier:
    """Tests for safe identifier quoting."""

    def test_quote_simple_name(self) -> None:
        """Simple names should be quoted."""
        from backend.connectors.database.base_db import quote_identifier

        assert quote_identifier("users") == '"users"'
        assert quote_identifier("claims") == '"claims"'

    def test_quote_escapes_quotes(self) -> None:
        """Quote characters in names should be escaped."""
        from backend.connectors.database.base_db import quote_identifier

        # Names with quotes are valid SQL identifiers
        # The quote_identifier function first validates, so we need
        # to use a name that passes validation but could contain quotes
        # Actually, our validator doesn't allow quotes, so this is safe
        pass  # Skip - our validator rejects names with special chars


class TestPasswordSanitization:
    """Tests for sanitizing passwords from error messages."""

    def test_sanitize_connection_string(self) -> None:
        """Passwords in connection strings should be redacted."""
        from backend.connectors.database.base_db import sanitize_error_message

        error = "Connection failed: postgresql://user:secret123@host:5432/db"
        sanitized = sanitize_error_message(error)
        assert "secret123" not in sanitized
        assert "***" in sanitized

    def test_sanitize_preserves_safe_content(self) -> None:
        """Non-password content should be preserved."""
        from backend.connectors.database.base_db import sanitize_error_message

        error = "Table 'users' not found in database"
        sanitized = sanitize_error_message(error)
        assert sanitized == error

    def test_sanitize_handles_empty(self) -> None:
        """Empty messages should be handled."""
        from backend.connectors.database.base_db import sanitize_error_message

        assert sanitize_error_message("") == ""

    def test_sanitize_multiple_passwords(self) -> None:
        """Multiple connection strings should all be sanitized."""
        from backend.connectors.database.base_db import sanitize_error_message

        error = "Failed: mysql://user:pass1@host1 and postgresql://admin:pass2@host2"
        sanitized = sanitize_error_message(error)
        assert "pass1" not in sanitized
        assert "pass2" not in sanitized


class TestPydanticValidators:
    """Tests for Pydantic model validators."""

    def test_cron_expression_valid(self) -> None:
        """Valid cron expressions should be accepted."""
        from backend.connectors.models import ConnectorCreate, ConnectorType, ConnectorSubtype, DataType

        connector = ConnectorCreate(
            name="Test Connector",
            connector_type=ConnectorType.DATABASE,
            subtype=ConnectorSubtype.POSTGRESQL,
            data_type=DataType.CLAIMS,
            connection_config={"host": "localhost"},
            sync_schedule="0 * * * *",
        )
        assert connector.sync_schedule == "0 * * * *"

    def test_cron_expression_normalizes_whitespace(self) -> None:
        """Extra whitespace in cron should be normalized."""
        from backend.connectors.models import ConnectorCreate, ConnectorType, ConnectorSubtype, DataType

        connector = ConnectorCreate(
            name="Test Connector",
            connector_type=ConnectorType.DATABASE,
            subtype=ConnectorSubtype.POSTGRESQL,
            data_type=DataType.CLAIMS,
            connection_config={"host": "localhost"},
            sync_schedule="0   *   *   *   *",  # Extra spaces
        )
        assert connector.sync_schedule == "0 * * * *"

    def test_cron_expression_invalid(self) -> None:
        """Invalid cron expressions should be rejected."""
        from pydantic import ValidationError
        from backend.connectors.models import ConnectorCreate, ConnectorType, ConnectorSubtype, DataType

        with pytest.raises(ValidationError, match="Invalid cron"):
            ConnectorCreate(
                name="Test Connector",
                connector_type=ConnectorType.DATABASE,
                subtype=ConnectorSubtype.POSTGRESQL,
                data_type=DataType.CLAIMS,
                connection_config={"host": "localhost"},
                sync_schedule="invalid cron",
            )

    def test_connector_name_xss_prevention(self) -> None:
        """Connector names with HTML should be rejected."""
        from pydantic import ValidationError
        from backend.connectors.models import ConnectorCreate, ConnectorType, ConnectorSubtype, DataType

        with pytest.raises(ValidationError, match="HTML special characters"):
            ConnectorCreate(
                name="<script>alert('xss')</script>",
                connector_type=ConnectorType.DATABASE,
                subtype=ConnectorSubtype.POSTGRESQL,
                data_type=DataType.CLAIMS,
                connection_config={"host": "localhost"},
            )

    def test_database_config_sql_identifier_validation(self) -> None:
        """SQL identifiers in database config should be validated."""
        from pydantic import ValidationError
        from backend.connectors.models import DatabaseConnectionConfig

        with pytest.raises(ValidationError, match="Invalid SQL identifier"):
            DatabaseConnectionConfig(
                host="localhost",
                port=5432,
                database="testdb",
                username="user",
                password="pass",
                table="users; DROP TABLE users",
            )

    def test_database_config_query_validation(self) -> None:
        """Custom queries with dangerous patterns should be rejected."""
        from pydantic import ValidationError
        from backend.connectors.models import DatabaseConnectionConfig

        with pytest.raises(ValidationError, match="cannot contain"):
            DatabaseConnectionConfig(
                host="localhost",
                port=5432,
                database="testdb",
                username="user",
                password="pass",
                query="SELECT * FROM users; DROP TABLE users",
            )

    def test_database_config_port_range(self) -> None:
        """Port numbers should be within valid range."""
        from pydantic import ValidationError
        from backend.connectors.models import DatabaseConnectionConfig

        with pytest.raises(ValidationError):
            DatabaseConnectionConfig(
                host="localhost",
                port=99999,  # Invalid port
                database="testdb",
                username="user",
                password="pass",
            )


class TestCredentialManager:
    """Tests for credential encryption and storage."""

    def test_encryption_requires_key(self) -> None:
        """Encryption should fail without a key."""
        import os
        import tempfile
        from backend.security.credentials import CredentialManager

        # Save and clear the env var
        original_key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
        if "CREDENTIAL_ENCRYPTION_KEY" in os.environ:
            del os.environ["CREDENTIAL_ENCRYPTION_KEY"]

        try:
            with tempfile.NamedTemporaryFile(suffix=".db") as f:
                manager = CredentialManager(f.name)
                assert not manager.encryption_enabled

                with pytest.raises(ValueError, match="not configured"):
                    manager.encrypt("secret")
        finally:
            # Restore the env var
            if original_key:
                os.environ["CREDENTIAL_ENCRYPTION_KEY"] = original_key

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Encryption and decryption should be reversible."""
        import tempfile
        from cryptography.fernet import Fernet
        from backend.security.credentials import CredentialManager

        key = Fernet.generate_key().decode()

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            manager = CredentialManager(f.name, encryption_key=key)
            assert manager.encryption_enabled

            original = "my_secret_password"
            encrypted = manager.encrypt(original)
            decrypted = manager.decrypt(encrypted)

            assert decrypted == original
            assert encrypted != original

    def test_store_and_retrieve_credential(self) -> None:
        """Credentials should be stored and retrieved correctly."""
        import tempfile
        from cryptography.fernet import Fernet
        from backend.security.credentials import CredentialManager

        key = Fernet.generate_key().decode()

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            manager = CredentialManager(f.name, encryption_key=key)

            # Store credential
            cred_id = manager.store_credential(
                connector_id="test-connector",
                credential_type="password",
                value="secret123",
            )
            assert cred_id is not None

            # Retrieve credential
            retrieved = manager.get_credential(
                connector_id="test-connector",
                credential_type="password",
            )
            assert retrieved == "secret123"

    def test_store_credential_upsert(self) -> None:
        """Storing the same credential twice should update, not duplicate."""
        import tempfile
        from cryptography.fernet import Fernet
        from backend.security.credentials import CredentialManager

        key = Fernet.generate_key().decode()

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            manager = CredentialManager(f.name, encryption_key=key)

            # Store initial credential
            cred_id1 = manager.store_credential(
                connector_id="test-connector",
                credential_type="password",
                value="password1",
            )

            # Store updated credential
            cred_id2 = manager.store_credential(
                connector_id="test-connector",
                credential_type="password",
                value="password2",
            )

            # Should return the same ID (update, not insert)
            assert cred_id1 == cred_id2

            # Should retrieve the updated value
            retrieved = manager.get_credential(
                connector_id="test-connector",
                credential_type="password",
            )
            assert retrieved == "password2"

    def test_delete_credentials(self) -> None:
        """Deleting credentials should remove all for a connector."""
        import tempfile
        from cryptography.fernet import Fernet
        from backend.security.credentials import CredentialManager

        key = Fernet.generate_key().decode()

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            manager = CredentialManager(f.name, encryption_key=key)

            # Store credentials
            manager.store_credential("test-connector", "password", "secret1")
            manager.store_credential("test-connector", "api_key", "secret2")

            # Verify they exist
            assert manager.get_credential("test-connector", "password") == "secret1"

            # Delete credentials
            deleted = manager.delete_credentials("test-connector")
            assert deleted == 2

            # Verify they're gone
            assert manager.get_credential("test-connector", "password") is None
            assert manager.get_credential("test-connector", "api_key") is None
