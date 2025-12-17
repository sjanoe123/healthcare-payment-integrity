"""Pytest configuration and fixtures."""

from __future__ import annotations

import atexit
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# Add backend to path for imports
backend_path = str(Path(__file__).parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Set test database path before importing app
# Use a temp file instead of :memory: for SQLite compatibility with FastAPI
_temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_temp_db_path = _temp_db.name
os.environ["DB_PATH"] = _temp_db_path


def _cleanup_test_db() -> None:
    """Clean up temporary test database file."""
    if os.path.exists(_temp_db_path):
        try:
            os.unlink(_temp_db_path)
        except OSError:
            pass  # File may already be deleted or locked


# Register cleanup to run at exit
atexit.register(_cleanup_test_db)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db() -> None:
    """Pytest fixture to ensure test database cleanup after session."""
    yield
    _cleanup_test_db()


@pytest.fixture
def sample_claim() -> dict[str, Any]:
    """Sample claim for testing."""
    return {
        "claim_id": "TEST-001",
        "billed_amount": 530.00,
        "diagnosis_codes": ["J06.9", "M54.5"],
        "items": [
            {
                "procedure_code": "99214",
                "diagnosis_code": "J06.9",
                "quantity": 1,
                "line_amount": 150.00,
            },
            {
                "procedure_code": "99215",
                "diagnosis_code": "M54.5",
                "quantity": 1,
                "line_amount": 200.00,
            },
            {
                "procedure_code": "99213",
                "diagnosis_code": "J06.9",
                "quantity": 2,
                "line_amount": 180.00,
            },
        ],
        "provider": {
            "npi": "1234567890",
            "specialty": "internal medicine",
        },
        "member": {
            "age": 45,
            "gender": "F",
        },
    }


@pytest.fixture
def sample_datasets() -> dict[str, Any]:
    """Sample reference datasets for testing."""
    return {
        "ncci_ptp": {
            ("99213", "99214"): {"citation": "NCCI PTP Edit", "modifier": "25"},
            ("99214", "99215"): {"citation": "NCCI PTP Edit", "modifier": "25"},
        },
        "ncci_mue": {
            "99213": {"limit": 1},
            "99214": {"limit": 1},
            "99215": {"limit": 1},
        },
        "lcd": {
            "99213": {
                "diagnosis_codes": {"J06.9", "J20.9", "R05.9"},
                "age_ranges": [{"min": 0, "max": 120}],
            },
            "99214": {
                "diagnosis_codes": {"J06.9", "J20.9", "M54.5"},
                "age_ranges": [{"min": 0, "max": 120}],
            },
        },
        "oig_exclusions": {"1234567890"},
        "fwa_watchlist": set(),
        "mpfs": {
            "99213": {"regions": {"national": 95.0}},
            "99214": {"regions": {"national": 130.0}},
            "99215": {"regions": {"national": 175.0}},
        },
        "utilization": {},
        "fwa_config": {
            "roi_multiplier": 1.0,
            "volume_threshold": 3,
            "high_risk_specialties": ["pain management"],
        },
    }


@pytest.fixture
def clean_claim() -> dict[str, Any]:
    """A claim with no fraud indicators."""
    return {
        "claim_id": "CLEAN-001",
        "billed_amount": 130.00,
        "diagnosis_codes": ["J06.9"],
        "items": [
            {
                "procedure_code": "99214",
                "diagnosis_code": "J06.9",
                "quantity": 1,
                "line_amount": 130.00,
            },
        ],
        "provider": {
            "npi": "9999999999",
            "specialty": "family medicine",
        },
        "member": {
            "age": 35,
            "gender": "M",
        },
    }
