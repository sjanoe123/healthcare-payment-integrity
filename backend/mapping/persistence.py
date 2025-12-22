"""Persistence layer for field mapping decisions.

This module provides storage and versioning for approved field mappings,
enabling audit trails and continuous improvement of the mapping system.

Usage:
    store = MappingStore(db_path)
    store.save_mapping(source_schema_id, field_mappings)
    mapping = store.get_mapping(source_schema_id)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MappingAction(str, Enum):
    """Actions that can be performed on a mapping."""

    CREATED = "created"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    ARCHIVED = "archived"


class MappingStatus(str, Enum):
    """Status of a field mapping."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


@dataclass
class FieldMappingEntry:
    """A single field mapping with confidence and approval info."""

    source_field: str
    target_field: str
    confidence: float
    method: str  # 'alias', 'semantic', 'llm_rerank', 'manual'
    reasoning: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None


@dataclass
class SchemaMapping:
    """A complete mapping for a source schema."""

    id: str
    source_schema_id: str
    source_schema_version: int
    target_schema: str
    field_mappings: list[FieldMappingEntry]
    status: MappingStatus
    created_at: str
    created_by: str | None = None
    approved_at: str | None = None
    approved_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "source_schema_id": self.source_schema_id,
            "source_schema_version": self.source_schema_version,
            "target_schema": self.target_schema,
            "field_mappings": [
                {
                    "source_field": m.source_field,
                    "target_field": m.target_field,
                    "confidence": m.confidence,
                    "method": m.method,
                    "reasoning": m.reasoning,
                    "approved_by": m.approved_by,
                    "approved_at": m.approved_at,
                }
                for m in self.field_mappings
            ],
            "status": self.status.value,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
        }


@dataclass
class AuditLogEntry:
    """An audit log entry for mapping changes."""

    id: str
    mapping_id: str
    action: MappingAction
    actor: str
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "mapping_id": self.mapping_id,
            "action": self.action.value,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "details": self.details,
        }


class MappingStore:
    """Storage for field mapping decisions with versioning and audit trail.

    Attributes:
        db_path: Path to the SQLite database
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the mapping store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_tables()

    def _init_tables(self) -> None:
        """Initialize database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Schema mappings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_mappings (
                    id TEXT PRIMARY KEY,
                    source_schema_id TEXT NOT NULL,
                    source_schema_version INTEGER NOT NULL,
                    target_schema TEXT DEFAULT 'omop_cdm_5.4',
                    field_mappings TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    created_by TEXT,
                    approved_at TEXT,
                    approved_by TEXT
                )
            """)

            # Audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mapping_audit_log (
                    id TEXT PRIMARY KEY,
                    mapping_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT,
                    FOREIGN KEY (mapping_id) REFERENCES schema_mappings(id)
                )
            """)

            # Indices for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mappings_source
                ON schema_mappings(source_schema_id, source_schema_version DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mappings_status
                ON schema_mappings(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_mapping
                ON mapping_audit_log(mapping_id, timestamp DESC)
            """)

            conn.commit()
            logger.info("Mapping persistence tables initialized")

    def save_mapping(
        self,
        source_schema_id: str,
        field_mappings: list[dict[str, Any]],
        created_by: str | None = None,
        target_schema: str = "omop_cdm_5.4",
    ) -> SchemaMapping:
        """Save a new schema mapping.

        Args:
            source_schema_id: Identifier for the source schema
            field_mappings: List of field mapping entries
            created_by: User who created the mapping
            target_schema: Target schema name

        Returns:
            The created SchemaMapping
        """
        mapping_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Get next version for this source schema
        version = self._get_next_version(source_schema_id)

        # Convert field mappings to entries
        entries = [
            FieldMappingEntry(
                source_field=m["source_field"],
                target_field=m["target_field"],
                confidence=m.get("confidence", 1.0),
                method=m.get("method", "manual"),
                reasoning=m.get("reasoning"),
                approved_by=m.get("approved_by"),
                approved_at=m.get("approved_at"),
            )
            for m in field_mappings
        ]

        mapping = SchemaMapping(
            id=mapping_id,
            source_schema_id=source_schema_id,
            source_schema_version=version,
            target_schema=target_schema,
            field_mappings=entries,
            status=MappingStatus.PENDING,
            created_at=now,
            created_by=created_by,
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO schema_mappings
                (id, source_schema_id, source_schema_version, target_schema,
                 field_mappings, status, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mapping.id,
                    mapping.source_schema_id,
                    mapping.source_schema_version,
                    mapping.target_schema,
                    json.dumps([m.__dict__ for m in mapping.field_mappings]),
                    mapping.status.value,
                    mapping.created_at,
                    mapping.created_by,
                ),
            )
            conn.commit()

        # Log the creation
        self._log_action(
            mapping_id,
            MappingAction.CREATED,
            created_by or "system",
            {
                "source_schema_id": source_schema_id,
                "version": version,
                "field_count": len(field_mappings),
            },
        )

        logger.info(f"Created mapping {mapping_id} for {source_schema_id} v{version}")
        return mapping

    def get_mapping(
        self,
        source_schema_id: str,
        version: int | None = None,
    ) -> SchemaMapping | None:
        """Get a schema mapping.

        Args:
            source_schema_id: Identifier for the source schema
            version: Optional specific version (latest if None)

        Returns:
            SchemaMapping or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if version is not None:
                cursor.execute(
                    """
                    SELECT * FROM schema_mappings
                    WHERE source_schema_id = ? AND source_schema_version = ?
                    """,
                    (source_schema_id, version),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM schema_mappings
                    WHERE source_schema_id = ?
                    ORDER BY source_schema_version DESC
                    LIMIT 1
                    """,
                    (source_schema_id,),
                )

            row = cursor.fetchone()
            if not row:
                return None

            return self._row_to_mapping(row)

    def get_mapping_by_id(self, mapping_id: str) -> SchemaMapping | None:
        """Get a mapping by its ID.

        Args:
            mapping_id: The mapping's unique ID

        Returns:
            SchemaMapping or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM schema_mappings WHERE id = ?", (mapping_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_mapping(row)

    def list_mappings(
        self,
        status: MappingStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SchemaMapping]:
        """List schema mappings.

        Args:
            status: Optional filter by status
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of SchemaMapping objects
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    """
                    SELECT * FROM schema_mappings
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (status.value, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM schema_mappings
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            return [self._row_to_mapping(row) for row in cursor.fetchall()]

    def approve_mapping(
        self,
        mapping_id: str,
        approved_by: str,
    ) -> SchemaMapping | None:
        """Approve a mapping.

        Args:
            mapping_id: The mapping's ID
            approved_by: User approving the mapping

        Returns:
            Updated SchemaMapping or None if not found
        """
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE schema_mappings
                SET status = ?, approved_at = ?, approved_by = ?
                WHERE id = ?
                """,
                (MappingStatus.APPROVED.value, now, approved_by, mapping_id),
            )
            conn.commit()

            if cursor.rowcount == 0:
                return None

        self._log_action(mapping_id, MappingAction.APPROVED, approved_by, {})
        logger.info(f"Approved mapping {mapping_id} by {approved_by}")

        return self.get_mapping_by_id(mapping_id)

    def reject_mapping(
        self,
        mapping_id: str,
        rejected_by: str,
        reason: str | None = None,
    ) -> SchemaMapping | None:
        """Reject a mapping.

        Args:
            mapping_id: The mapping's ID
            rejected_by: User rejecting the mapping
            reason: Optional rejection reason

        Returns:
            Updated SchemaMapping or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE schema_mappings
                SET status = ?
                WHERE id = ?
                """,
                (MappingStatus.REJECTED.value, mapping_id),
            )
            conn.commit()

            if cursor.rowcount == 0:
                return None

        self._log_action(
            mapping_id,
            MappingAction.REJECTED,
            rejected_by,
            {
                "reason": reason,
            },
        )
        logger.info(f"Rejected mapping {mapping_id} by {rejected_by}")

        return self.get_mapping_by_id(mapping_id)

    def get_audit_log(
        self,
        mapping_id: str,
        limit: int = 50,
    ) -> list[AuditLogEntry]:
        """Get audit log for a mapping.

        Args:
            mapping_id: The mapping's ID
            limit: Maximum entries to return

        Returns:
            List of AuditLogEntry objects
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM mapping_audit_log
                WHERE mapping_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (mapping_id, limit),
            )

            return [
                AuditLogEntry(
                    id=row[0],
                    mapping_id=row[1],
                    action=MappingAction(row[2]),
                    actor=row[3],
                    timestamp=row[4],
                    details=json.loads(row[5]) if row[5] else {},
                )
                for row in cursor.fetchall()
            ]

    def _get_next_version(self, source_schema_id: str) -> int:
        """Get the next version number for a source schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT MAX(source_schema_version) FROM schema_mappings
                WHERE source_schema_id = ?
                """,
                (source_schema_id,),
            )
            result = cursor.fetchone()[0]
            return (result or 0) + 1

    def _log_action(
        self,
        mapping_id: str,
        action: MappingAction,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        """Log an action to the audit trail."""
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO mapping_audit_log
                (id, mapping_id, action, actor, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (log_id, mapping_id, action.value, actor, now, json.dumps(details)),
            )
            conn.commit()

    def _row_to_mapping(self, row: tuple) -> SchemaMapping:
        """Convert a database row to a SchemaMapping object."""
        field_mappings_data = json.loads(row[4])
        entries = [
            FieldMappingEntry(
                source_field=m["source_field"],
                target_field=m["target_field"],
                confidence=m.get("confidence", 1.0),
                method=m.get("method", "manual"),
                reasoning=m.get("reasoning"),
                approved_by=m.get("approved_by"),
                approved_at=m.get("approved_at"),
            )
            for m in field_mappings_data
        ]

        return SchemaMapping(
            id=row[0],
            source_schema_id=row[1],
            source_schema_version=row[2],
            target_schema=row[3],
            field_mappings=entries,
            status=MappingStatus(row[5]),
            created_at=row[6],
            created_by=row[7],
            approved_at=row[8],
            approved_by=row[9],
        )


# Global store instance (initialized lazily)
_store_instance: MappingStore | None = None


def get_mapping_store(db_path: str | None = None) -> MappingStore:
    """Get or create the global MappingStore instance.

    Args:
        db_path: Path to database (uses default if None)

    Returns:
        Singleton MappingStore instance
    """
    global _store_instance
    if _store_instance is None:
        import os

        path = db_path or os.getenv("DB_PATH", "data/prototype.db")
        _store_instance = MappingStore(path)
    return _store_instance
