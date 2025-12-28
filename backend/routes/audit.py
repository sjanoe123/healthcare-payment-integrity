"""Audit logging routes for HIPAA compliance.

Provides endpoints for:
- Listing audit log entries
- Exporting audit logs for compliance review
- Filtering by date range, action type, user, and resource

Security Note:
    These endpoints should be protected by authentication middleware in production.
    Access to audit logs should be restricted to authorized personnel only (e.g.,
    compliance officers, security admins). Consider adding role-based access control
    via FastAPI dependencies when implementing authentication.

    TODO: Implement authentication middleware before production deployment.
    Track this in your issue tracker to ensure it's not forgotten.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

router = APIRouter(prefix="/api/audit", tags=["audit"])

# Thread-safe initialization flag with lock
# Prevents race conditions when multiple async handlers check/set the flag
_audit_table_initialized = False
_audit_table_lock = threading.Lock()

# Maximum rows for export to prevent memory issues
# Configurable via AUDIT_MAX_EXPORT_ROWS environment variable
MAX_EXPORT_ROWS = int(os.environ.get("AUDIT_MAX_EXPORT_ROWS", "10000"))


class AuditAction(str, Enum):
    """Types of auditable actions."""

    # Claim analysis
    CLAIM_UPLOAD = "claim.upload"
    CLAIM_ANALYZE = "claim.analyze"
    CLAIM_VIEW = "claim.view"

    # Connector management
    CONNECTOR_CREATE = "connector.create"
    CONNECTOR_UPDATE = "connector.update"
    CONNECTOR_DELETE = "connector.delete"
    CONNECTOR_TEST = "connector.test"
    CONNECTOR_SYNC = "connector.sync"

    # Policy management
    POLICY_UPLOAD = "policy.upload"
    POLICY_DELETE = "policy.delete"
    POLICY_SEARCH = "policy.search"

    # System
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    EXPORT_AUDIT = "audit.export"


class AuditLogEntry(BaseModel):
    """Single audit log entry."""

    id: str
    timestamp: str
    action: str
    user_id: str | None = None
    user_email: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    status: str = "success"
    error_message: str | None = None


class AuditLogListResponse(BaseModel):
    """Response for audit log listing."""

    entries: list[AuditLogEntry]
    total: int
    limit: int
    offset: int
    filters_applied: dict[str, Any]


class AuditStats(BaseModel):
    """Summary statistics for audit logs."""

    total_entries: int
    entries_by_action: dict[str, int]
    entries_by_status: dict[str, int]
    entries_by_user: dict[str, int]
    date_range: dict[str, str]


def get_db():
    """Get database connection."""
    import os

    db_path = os.environ.get("DB_PATH", "prototype.db")
    return sqlite3.connect(db_path, check_same_thread=False)


def init_audit_table(conn: sqlite3.Connection) -> None:
    """Initialize the audit_logs table if it doesn't exist.

    Uses a module-level flag with thread lock to avoid redundant schema checks
    on every request. The CREATE TABLE IF NOT EXISTS is idempotent but involves
    disk I/O, so we skip it after first successful initialization.

    Thread-safe via _audit_table_lock to prevent race conditions in async handlers.
    """
    global _audit_table_initialized

    # Fast path: already initialized (no lock needed for read)
    if _audit_table_initialized:
        return

    # Slow path: acquire lock and double-check
    with _audit_table_lock:
        # Double-check after acquiring lock (another thread may have initialized)
        if _audit_table_initialized:
            return

        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                user_id TEXT,
                user_email TEXT,
                resource_type TEXT,
                resource_id TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                status TEXT DEFAULT 'success',
                error_message TEXT
            )
        """)

        # Create indices for common queries
        # Consider adding composite index for (action, timestamp) for common filter patterns
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type, resource_id)"
        )
        # Composite index for common filter: action + timestamp
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_action_time ON audit_logs(action, timestamp)"
        )

        conn.commit()
        _audit_table_initialized = True


def log_audit_event(
    conn: sqlite3.Connection,
    action: str,
    user_id: str | None = None,
    user_email: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    status: str = "success",
    error_message: str | None = None,
) -> str:
    """Log an audit event to the database.

    Returns the audit log entry ID.
    """
    import uuid

    audit_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO audit_logs (
            id, timestamp, action, user_id, user_email,
            resource_type, resource_id, details,
            ip_address, user_agent, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            timestamp,
            action,
            user_id,
            user_email,
            resource_type,
            resource_id,
            json.dumps(details) if details else None,
            ip_address,
            user_agent,
            status,
            error_message,
        ),
    )
    conn.commit()

    return audit_id


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, description="Filter by action type"),
    user_id: str | None = Query(default=None, description="Filter by user ID"),
    resource_type: str | None = Query(
        default=None, description="Filter by resource type"
    ),
    resource_id: str | None = Query(default=None, description="Filter by resource ID"),
    status: str | None = Query(
        default=None, description="Filter by status (success/error)"
    ),
    start_date: str | None = Query(default=None, description="Start date (ISO format)"),
    end_date: str | None = Query(default=None, description="End date (ISO format)"),
) -> AuditLogListResponse:
    """List audit log entries with filtering and pagination."""
    conn = get_db()
    init_audit_table(conn)
    cursor = conn.cursor()

    # Build query with filters
    conditions = []
    params: list[Any] = []

    if action:
        conditions.append("action = ?")
        params.append(action)

    if user_id:
        conditions.append("user_id = ?")
        params.append(user_id)

    if resource_type:
        conditions.append("resource_type = ?")
        params.append(resource_type)

    if resource_id:
        conditions.append("resource_id = ?")
        params.append(resource_id)

    if status:
        conditions.append("status = ?")
        params.append(status)

    if start_date:
        conditions.append("timestamp >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("timestamp <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # SAFETY NOTE: The where_clause is constructed from hardcoded column names only
    # (action, user_id, resource_type, resource_id, status, timestamp).
    # User input is passed via parameterized queries (?), preventing SQL injection.
    # Get total count
    cursor.execute(f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}", params)
    total = cursor.fetchone()[0]

    # Get entries
    cursor.execute(
        f"""
        SELECT id, timestamp, action, user_id, user_email,
               resource_type, resource_id, details,
               ip_address, user_agent, status, error_message
        FROM audit_logs
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )

    entries = []
    for row in cursor.fetchall():
        details = None
        if row[7]:
            try:
                details = json.loads(row[7])
            except json.JSONDecodeError:
                details = {"raw": row[7]}

        entries.append(
            AuditLogEntry(
                id=row[0],
                timestamp=row[1],
                action=row[2],
                user_id=row[3],
                user_email=row[4],
                resource_type=row[5],
                resource_id=row[6],
                details=details,
                ip_address=row[8],
                user_agent=row[9],
                status=row[10] or "success",
                error_message=row[11],
            )
        )

    conn.close()

    return AuditLogListResponse(
        entries=entries,
        total=total,
        limit=limit,
        offset=offset,
        filters_applied={
            "action": action,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
        },
    )


@router.get("/stats", response_model=AuditStats)
async def get_audit_stats(
    start_date: str | None = Query(default=None, description="Start date (ISO format)"),
    end_date: str | None = Query(default=None, description="End date (ISO format)"),
) -> AuditStats:
    """Get summary statistics for audit logs."""
    conn = get_db()
    init_audit_table(conn)
    cursor = conn.cursor()

    # Build date filter
    conditions = []
    params: list[Any] = []

    if start_date:
        conditions.append("timestamp >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("timestamp <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Total entries
    cursor.execute(f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}", params)
    total_entries = cursor.fetchone()[0]

    # By action
    cursor.execute(
        f"""
        SELECT action, COUNT(*) FROM audit_logs
        WHERE {where_clause}
        GROUP BY action
        """,
        params,
    )
    entries_by_action = dict(cursor.fetchall())

    # By status
    cursor.execute(
        f"""
        SELECT COALESCE(status, 'success'), COUNT(*) FROM audit_logs
        WHERE {where_clause}
        GROUP BY status
        """,
        params,
    )
    entries_by_status = dict(cursor.fetchall())

    # By user (top 10)
    cursor.execute(
        f"""
        SELECT COALESCE(user_id, 'anonymous'), COUNT(*) FROM audit_logs
        WHERE {where_clause}
        GROUP BY user_id
        ORDER BY COUNT(*) DESC
        LIMIT 10
        """,
        params,
    )
    entries_by_user = dict(cursor.fetchall())

    # Date range
    cursor.execute(
        f"""
        SELECT MIN(timestamp), MAX(timestamp) FROM audit_logs
        WHERE {where_clause}
        """,
        params,
    )
    row = cursor.fetchone()
    date_range = {
        "earliest": row[0] or "",
        "latest": row[1] or "",
    }

    conn.close()

    return AuditStats(
        total_entries=total_entries,
        entries_by_action=entries_by_action,
        entries_by_status=entries_by_status,
        entries_by_user=entries_by_user,
        date_range=date_range,
    )


@router.get("/export")
async def export_audit_logs(
    format: str = Query(default="csv", description="Export format: csv or json"),
    start_date: str | None = Query(default=None, description="Start date (ISO format)"),
    end_date: str | None = Query(default=None, description="End date (ISO format)"),
    action: str | None = Query(default=None, description="Filter by action type"),
    limit: int = Query(
        default=MAX_EXPORT_ROWS,
        ge=1,
        le=MAX_EXPORT_ROWS,
        description=f"Maximum rows to export (max {MAX_EXPORT_ROWS})",
    ),
) -> Response:
    """Export audit logs for compliance review.

    Returns CSV or JSON format for external analysis tools.
    Limited to MAX_EXPORT_ROWS rows to prevent memory issues.
    For larger exports, use date range filters to batch the export.
    """
    conn = get_db()
    init_audit_table(conn)
    cursor = conn.cursor()

    # Log the export action itself
    log_audit_event(
        conn,
        action=AuditAction.EXPORT_AUDIT.value,
        resource_type="audit_logs",
        details={
            "format": format,
            "start_date": start_date,
            "end_date": end_date,
            "action_filter": action,
        },
    )

    # Build query with filters
    conditions = []
    params: list[Any] = []

    if start_date:
        conditions.append("timestamp >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("timestamp <= ?")
        params.append(end_date)

    if action:
        conditions.append("action = ?")
        params.append(action)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # SAFETY NOTE: where_clause uses hardcoded column names; user input is parameterized
    cursor.execute(
        f"""
        SELECT id, timestamp, action, user_id, user_email,
               resource_type, resource_id, details,
               ip_address, user_agent, status, error_message
        FROM audit_logs
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        params + [limit],
    )

    rows = cursor.fetchall()
    conn.close()

    if format == "json":
        # JSON export
        entries = []
        for row in rows:
            details = None
            if row[7]:
                try:
                    details = json.loads(row[7])
                except json.JSONDecodeError:
                    details = {"raw": row[7]}

            entries.append(
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "action": row[2],
                    "user_id": row[3],
                    "user_email": row[4],
                    "resource_type": row[5],
                    "resource_id": row[6],
                    "details": details,
                    "ip_address": row[8],
                    "user_agent": row[9],
                    "status": row[10] or "success",
                    "error_message": row[11],
                }
            )

        content = json.dumps(
            {
                "audit_logs": entries,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        filename = (
            f"audit_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        )

        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    else:
        # CSV export (default)
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow(
            [
                "ID",
                "Timestamp",
                "Action",
                "User ID",
                "User Email",
                "Resource Type",
                "Resource ID",
                "Details",
                "IP Address",
                "User Agent",
                "Status",
                "Error Message",
            ]
        )

        # Data rows
        for row in rows:
            writer.writerow(row)

        content = output.getvalue()
        filename = (
            f"audit_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        )

        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.get("/actions")
async def list_audit_actions() -> dict[str, Any]:
    """List all available audit action types."""
    return {
        "actions": [action.value for action in AuditAction],
        "categories": {
            "claim": [a.value for a in AuditAction if a.value.startswith("claim.")],
            "connector": [
                a.value for a in AuditAction if a.value.startswith("connector.")
            ],
            "policy": [a.value for a in AuditAction if a.value.startswith("policy.")],
            "auth": [a.value for a in AuditAction if a.value.startswith("auth.")],
            "audit": [a.value for a in AuditAction if a.value.startswith("audit.")],
        },
    }
