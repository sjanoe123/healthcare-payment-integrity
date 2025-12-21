"""Date parsing utilities for healthcare claims processing."""

from __future__ import annotations

from datetime import datetime


def parse_flexible_date(date_str: str | None) -> datetime | None:
    """Parse date from multiple common formats.

    Supports the following formats:
    - ISO 8601: YYYY-MM-DD (e.g., 2024-01-15)
    - US format: MM/DD/YYYY (e.g., 01/15/2024)
    - Compact: YYYYMMDD (e.g., 20240115)

    Args:
        date_str: Date string to parse, or None

    Returns:
        Parsed datetime object, or None if parsing fails or input is None

    Examples:
        >>> parse_flexible_date("2024-01-15")
        datetime.datetime(2024, 1, 15, 0, 0)
        >>> parse_flexible_date("01/15/2024")
        datetime.datetime(2024, 1, 15, 0, 0)
        >>> parse_flexible_date("20240115")
        datetime.datetime(2024, 1, 15, 0, 0)
        >>> parse_flexible_date(None)
        None
        >>> parse_flexible_date("invalid")
        None
    """
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",  # ISO 8601
        "%m/%d/%Y",  # US format
        "%Y%m%d",  # Compact
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None
