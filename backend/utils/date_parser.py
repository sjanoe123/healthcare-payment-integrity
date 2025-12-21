"""Date parsing utilities for healthcare claims processing."""

from __future__ import annotations

from datetime import datetime

# Reasonable date bounds for healthcare claims
MIN_VALID_YEAR = 1900
MAX_VALID_YEAR = 2100


def parse_flexible_date(date_str: str | None) -> datetime | None:
    """Parse date from multiple common formats with validation.

    Supports the following formats:
    - ISO 8601: YYYY-MM-DD (e.g., 2024-01-15)
    - US format: MM/DD/YYYY (e.g., 01/15/2024)
    - Compact: YYYYMMDD (e.g., 20240115)

    Validates that:
    - The date is a real calendar date (no Feb 30, etc.)
    - The year is between 1900 and 2100 (sensible for healthcare claims)

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
        >>> parse_flexible_date("2024-02-30")  # Invalid date
        None
        >>> parse_flexible_date("00/00/0000")  # Invalid date
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
            parsed = datetime.strptime(date_str, fmt)
            # Validate year is within sensible bounds
            if parsed.year < MIN_VALID_YEAR or parsed.year > MAX_VALID_YEAR:
                continue
            return parsed
        except ValueError:
            # strptime raises ValueError for invalid dates like Feb 30
            continue

    return None
