"""Credential encryption and management.

Uses Fernet symmetric encryption for secure storage of sensitive
connector credentials (passwords, API keys, etc.).

Environment variable CREDENTIAL_ENCRYPTION_KEY must be set with a valid
Fernet key. Generate with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import base64
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# Try to import cryptography, provide helpful error if missing
try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    logger.warning(
        "cryptography package not installed - credential encryption disabled"
    )


class CredentialManager:
    """Manages encrypted storage of connector credentials.

    Credentials are encrypted using Fernet (AES-128-CBC with HMAC)
    and stored in SQLite alongside connector configurations.
    """

    def __init__(self, db_path: str, encryption_key: str | None = None) -> None:
        """Initialize the credential manager.

        Args:
            db_path: Path to the SQLite database
            encryption_key: Fernet key for encryption (defaults to env var)
        """
        self.db_path = db_path
        self._key = encryption_key or os.getenv("CREDENTIAL_ENCRYPTION_KEY")
        self._fernet: Any = None

        if self._key and Fernet:
            try:
                self._fernet = Fernet(self._key.encode())
            except Exception as e:
                logger.error(f"Invalid encryption key: {e}")
                self._fernet = None

        self._init_table()

    def _init_table(self) -> None:
        """Create the credentials table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS connector_credentials (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    credential_type TEXT NOT NULL,
                    encrypted_value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(connector_id, credential_type)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_credentials_connector
                ON connector_credentials(connector_id)
            """)

    @property
    def encryption_enabled(self) -> bool:
        """Check if encryption is properly configured."""
        return self._fernet is not None

    def encrypt(self, value: str) -> str:
        """Encrypt a string value.

        Args:
            value: Plain text value to encrypt

        Returns:
            Base64-encoded encrypted value

        Raises:
            ValueError: If encryption is not configured
        """
        if not self._fernet:
            raise ValueError(
                "Encryption not configured. Set CREDENTIAL_ENCRYPTION_KEY env var."
            )

        encrypted = self._fernet.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_value: str) -> str:
        """Decrypt an encrypted value.

        Args:
            encrypted_value: Base64-encoded encrypted value

        Returns:
            Decrypted plain text

        Raises:
            ValueError: If decryption fails
        """
        if not self._fernet:
            raise ValueError("Encryption not configured")

        try:
            decoded = base64.urlsafe_b64decode(encrypted_value.encode())
            return self._fernet.decrypt(decoded).decode()
        except InvalidToken:
            raise ValueError("Invalid encrypted value or wrong key")

    def store_credential(
        self,
        connector_id: str,
        credential_type: str,
        value: str,
    ) -> str:
        """Store an encrypted credential.

        Args:
            connector_id: ID of the connector
            credential_type: Type of credential (e.g., 'password', 'api_key')
            value: Plain text credential value

        Returns:
            ID of the stored credential
        """
        encrypted = self.encrypt(value)
        now = datetime.utcnow().isoformat()
        new_id = str(uuid4())

        with sqlite3.connect(self.db_path) as conn:
            # Use atomic ON CONFLICT to avoid TOCTOU race condition
            # The new_id is only used if this is an insert, not an update
            conn.execute(
                """
                INSERT INTO connector_credentials
                    (id, connector_id, credential_type, encrypted_value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(connector_id, credential_type) DO UPDATE SET
                    encrypted_value = excluded.encrypted_value,
                    updated_at = excluded.updated_at
                """,
                (new_id, connector_id, credential_type, encrypted, now, now),
            )
            conn.commit()

            # Get the actual ID (either the new one or the existing one)
            cursor = conn.execute(
                """
                SELECT id FROM connector_credentials
                WHERE connector_id = ? AND credential_type = ?
                """,
                (connector_id, credential_type),
            )
            row = cursor.fetchone()
            cred_id = row[0] if row else new_id

        logger.debug(
            f"Stored credential {credential_type} for connector {connector_id}"
        )
        return cred_id

    def get_credential(
        self,
        connector_id: str,
        credential_type: str,
    ) -> str | None:
        """Retrieve and decrypt a credential.

        Args:
            connector_id: ID of the connector
            credential_type: Type of credential

        Returns:
            Decrypted credential value, or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT encrypted_value FROM connector_credentials
                WHERE connector_id = ? AND credential_type = ?
                """,
                (connector_id, credential_type),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return self.decrypt(row[0])

    def delete_credentials(self, connector_id: str) -> int:
        """Delete all credentials for a connector.

        Args:
            connector_id: ID of the connector

        Returns:
            Number of credentials deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM connector_credentials WHERE connector_id = ?",
                (connector_id,),
            )
            conn.commit()
            return cursor.rowcount

    def list_credential_types(self, connector_id: str) -> list[str]:
        """List credential types stored for a connector.

        Args:
            connector_id: ID of the connector

        Returns:
            List of credential type names
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT credential_type FROM connector_credentials
                WHERE connector_id = ?
                ORDER BY credential_type
                """,
                (connector_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    def extract_and_store_secrets(
        self,
        connector_id: str,
        config: dict[str, Any],
        secret_fields: list[str],
    ) -> dict[str, Any]:
        """Extract secrets from config, store them, and return sanitized config.

        Args:
            connector_id: ID of the connector
            config: Connection configuration with secrets
            secret_fields: List of field names that contain secrets

        Returns:
            Config with secrets removed (replaced with placeholder)
        """
        sanitized = config.copy()

        for field in secret_fields:
            if field in config and config[field]:
                self.store_credential(connector_id, field, config[field])
                sanitized[field] = "***ENCRYPTED***"

        return sanitized

    def inject_secrets(
        self,
        connector_id: str,
        config: dict[str, Any],
        secret_fields: list[str],
    ) -> dict[str, Any]:
        """Inject stored secrets back into a config.

        Args:
            connector_id: ID of the connector
            config: Sanitized configuration
            secret_fields: List of field names that contain secrets

        Returns:
            Config with secrets injected
        """
        result = config.copy()

        for field in secret_fields:
            value = self.get_credential(connector_id, field)
            if value:
                result[field] = value

        return result


# Global singleton instance
_credential_manager: CredentialManager | None = None


def get_credential_manager(db_path: str | None = None) -> CredentialManager:
    """Get or create the global CredentialManager instance.

    Args:
        db_path: Path to SQLite database (required on first call)

    Returns:
        Global CredentialManager instance
    """
    global _credential_manager

    if _credential_manager is None:
        if db_path is None:
            db_path = os.getenv("DB_PATH", "data/prototype.db")
        _credential_manager = CredentialManager(db_path)

    return _credential_manager


def encrypt_value(value: str) -> str:
    """Convenience function to encrypt a value.

    Args:
        value: Plain text to encrypt

    Returns:
        Encrypted value
    """
    return get_credential_manager().encrypt(value)


def decrypt_value(encrypted: str) -> str:
    """Convenience function to decrypt a value.

    Args:
        encrypted: Encrypted value

    Returns:
        Decrypted plain text
    """
    return get_credential_manager().decrypt(encrypted)
