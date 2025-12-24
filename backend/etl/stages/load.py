"""Load stage for ETL pipeline.

Handles data loading into target storage including:
- SQLite storage for claims, eligibility, providers
- Batch inserts with conflict handling
- Audit trail tracking
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """Result from a load operation."""

    inserted_count: int
    updated_count: int
    failed_count: int
    errors: list[dict[str, Any]] = field(default_factory=list)


class LoadStage:
    """Load stage for writing data to target storage.

    Handles batch inserts into SQLite with support for
    upserts and conflict resolution.
    """

    def __init__(
        self,
        db_path: str,
        table_name: str,
        data_type: str,
        primary_key: str = "id",
        batch_size: int = 100,
    ) -> None:
        """Initialize the load stage.

        Args:
            db_path: Path to SQLite database
            table_name: Target table name
            data_type: Data type (claims, eligibility, providers, reference)
            primary_key: Primary key column name
            batch_size: Records per insert batch
        """
        self.db_path = db_path
        self.table_name = table_name
        self.data_type = data_type
        self.primary_key = primary_key
        self.batch_size = batch_size
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        """Ensure target tables exist."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Create data table based on data type
            if self.data_type == "claims":
                self._create_claims_table(cursor)
            elif self.data_type == "eligibility":
                self._create_eligibility_table(cursor)
            elif self.data_type == "providers":
                self._create_providers_table(cursor)
            elif self.data_type == "reference":
                self._create_reference_table(cursor)
            else:
                # Generic table for unknown types
                self._create_generic_table(cursor)

            # Create audit table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name}_audit (
                    id TEXT PRIMARY KEY,
                    record_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    old_data TEXT,
                    new_data TEXT,
                    changed_at TEXT NOT NULL,
                    changed_by TEXT
                )
            """)

            conn.commit()
        finally:
            conn.close()

    def _create_claims_table(self, cursor: sqlite3.Cursor) -> None:
        """Create claims table."""
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                claim_id TEXT UNIQUE,
                patient_id TEXT,
                provider_npi TEXT,
                date_of_service TEXT,
                procedure_codes TEXT,
                diagnosis_codes TEXT,
                billed_amount REAL,
                allowed_amount REAL,
                paid_amount REAL,
                place_of_service TEXT,
                claim_type TEXT,
                status TEXT,
                raw_data TEXT,
                source_connector_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_claim_id
            ON {self.table_name}(claim_id)
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_patient_id
            ON {self.table_name}(patient_id)
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_date
            ON {self.table_name}(date_of_service)
        """)

    def _create_eligibility_table(self, cursor: sqlite3.Cursor) -> None:
        """Create eligibility table."""
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                member_id TEXT,
                patient_id TEXT,
                plan_id TEXT,
                plan_name TEXT,
                coverage_start TEXT,
                coverage_end TEXT,
                status TEXT,
                coverage_type TEXT,
                raw_data TEXT,
                source_connector_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_member_id
            ON {self.table_name}(member_id)
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_patient_id
            ON {self.table_name}(patient_id)
        """)

    def _create_providers_table(self, cursor: sqlite3.Cursor) -> None:
        """Create providers table."""
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                npi TEXT UNIQUE,
                name TEXT,
                specialty TEXT,
                taxonomy_code TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zip_code TEXT,
                phone TEXT,
                status TEXT,
                credentialing_date TEXT,
                raw_data TEXT,
                source_connector_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_npi
            ON {self.table_name}(npi)
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_specialty
            ON {self.table_name}(specialty)
        """)

    def _create_reference_table(self, cursor: sqlite3.Cursor) -> None:
        """Create reference data table."""
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                code TEXT,
                code_type TEXT,
                description TEXT,
                effective_date TEXT,
                termination_date TEXT,
                metadata TEXT,
                raw_data TEXT,
                source_connector_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_code
            ON {self.table_name}(code, code_type)
        """)

    def _create_generic_table(self, cursor: sqlite3.Cursor) -> None:
        """Create generic data table."""
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                source_connector_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

    def load(
        self,
        records: list[dict[str, Any]],
        source_connector_id: str | None = None,
        upsert: bool = True,
    ) -> LoadResult:
        """Load records into target storage.

        Args:
            records: Records to load
            source_connector_id: Source connector for tracking
            upsert: Whether to update existing records

        Returns:
            LoadResult with counts
        """
        inserted = 0
        updated = 0
        failed = 0
        errors = []

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            for idx, record in enumerate(records):
                try:
                    # Generate ID if not present
                    if self.primary_key not in record or not record[self.primary_key]:
                        record[self.primary_key] = str(uuid.uuid4())

                    record_id = record[self.primary_key]

                    # Add metadata
                    record["source_connector_id"] = source_connector_id
                    record["updated_at"] = now

                    # Check if exists
                    cursor.execute(
                        f"SELECT {self.primary_key} FROM {self.table_name} WHERE {self.primary_key} = ?",
                        (record_id,),
                    )
                    existing = cursor.fetchone()

                    if existing and upsert:
                        # Update existing
                        self._update_record(cursor, record, now)
                        updated += 1
                    elif not existing:
                        # Insert new
                        record["created_at"] = now
                        self._insert_record(cursor, record)
                        inserted += 1
                    else:
                        # Skip existing when not upserting
                        continue

                except Exception as e:
                    failed += 1
                    errors.append(
                        {
                            "record_index": idx,
                            "error": str(e),
                            "record_id": record.get(self.primary_key),
                        }
                    )
                    logger.debug(f"Load error at index {idx}: {e}")

            conn.commit()

        finally:
            conn.close()

        return LoadResult(
            inserted_count=inserted,
            updated_count=updated,
            failed_count=failed,
            errors=errors,
        )

    def _insert_record(self, cursor: sqlite3.Cursor, record: dict[str, Any]) -> None:
        """Insert a single record.

        Args:
            cursor: Database cursor
            record: Record to insert
        """
        # Get table columns
        columns = self._get_table_columns(cursor)

        # Filter record to matching columns
        filtered = {}
        extra_data = {}

        for key, value in record.items():
            if key in columns:
                filtered[key] = self._serialize_value(value)
            else:
                extra_data[key] = value

        # Store extra data in raw_data if column exists
        if "raw_data" in columns and extra_data:
            filtered["raw_data"] = json.dumps(extra_data)

        # Build insert
        cols = list(filtered.keys())
        placeholders = ["?" for _ in cols]

        cursor.execute(
            f"INSERT INTO {self.table_name} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})",
            [filtered[c] for c in cols],
        )

    def _update_record(
        self, cursor: sqlite3.Cursor, record: dict[str, Any], now: str
    ) -> None:
        """Update an existing record.

        Args:
            cursor: Database cursor
            record: Record to update
            now: Current timestamp
        """
        # Get table columns
        columns = self._get_table_columns(cursor)

        # Filter record to matching columns
        filtered = {}
        extra_data = {}

        for key, value in record.items():
            if key in columns and key != self.primary_key:
                filtered[key] = self._serialize_value(value)
            elif key not in columns:
                extra_data[key] = value

        # Store extra data in raw_data if column exists
        if "raw_data" in columns and extra_data:
            filtered["raw_data"] = json.dumps(extra_data)

        # Build update
        set_clause = ", ".join([f"{col} = ?" for col in filtered.keys()])
        values = list(filtered.values())
        values.append(record[self.primary_key])

        cursor.execute(
            f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?",
            values,
        )

    def _get_table_columns(self, cursor: sqlite3.Cursor) -> set[str]:
        """Get column names for the table.

        Args:
            cursor: Database cursor

        Returns:
            Set of column names
        """
        cursor.execute(f"PRAGMA table_info({self.table_name})")
        return {row[1] for row in cursor.fetchall()}

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for storage.

        Args:
            value: Value to serialize

        Returns:
            Serialized value
        """
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def add_audit_entry(
        self,
        record_id: str,
        operation: str,
        old_data: dict[str, Any] | None = None,
        new_data: dict[str, Any] | None = None,
        changed_by: str | None = None,
    ) -> None:
        """Add an audit trail entry.

        Args:
            record_id: ID of modified record
            operation: Operation type (insert, update, delete)
            old_data: Previous data
            new_data: New data
            changed_by: User who made change
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO {self.table_name}_audit
                (id, record_id, operation, old_data, new_data, changed_at, changed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    record_id,
                    operation,
                    json.dumps(old_data) if old_data else None,
                    json.dumps(new_data) if new_data else None,
                    datetime.now(timezone.utc).isoformat(),
                    changed_by,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_record_count(self) -> int:
        """Get total record count.

        Returns:
            Number of records
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def truncate(self) -> None:
        """Delete all records from the table."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.table_name}")
            conn.commit()
            logger.info(f"Truncated table {self.table_name}")
        finally:
            conn.close()
