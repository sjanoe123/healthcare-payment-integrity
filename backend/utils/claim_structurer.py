"""Utility for structuring claims for the rules engine.

The rules engine expects claims in a nested format with:
- member.member_id
- provider.npi
- claim_lines[].procedure_code
"""

from __future__ import annotations

import json
from typing import Any


def structure_claim_for_rules_engine(claim_record: dict[str, Any]) -> dict[str, Any]:
    """Structure a flat claim record for the rules engine.

    Transforms records from synced_claims table or ETL output into
    the nested format expected by evaluate_baseline().

    Args:
        claim_record: Flat claim record with keys like patient_id,
            provider_npi, procedure_codes, etc.

    Returns:
        Structured claim dict with nested member, provider, claim_lines
    """
    # Parse raw_data if present (contains extra fields from source)
    raw_data = {}
    if claim_record.get("raw_data"):
        try:
            raw_data = json.loads(claim_record["raw_data"])
        except (json.JSONDecodeError, TypeError):
            pass

    # Build structured claim
    claim_data = {
        "claim_id": claim_record.get("claim_id"),
        "member": {
            "member_id": claim_record.get("patient_id") or raw_data.get("member_id"),
        },
        "provider": {
            "npi": claim_record.get("provider_npi") or raw_data.get("npi"),
        },
        "date_of_service": claim_record.get("date_of_service"),
        "billed_amount": claim_record.get("billed_amount", 0),
        "place_of_service": claim_record.get("place_of_service", "11"),
    }

    # Parse procedure codes
    procedure_codes = parse_json_list(claim_record.get("procedure_codes"))

    # Parse diagnosis codes
    diagnosis_codes = parse_json_list(claim_record.get("diagnosis_codes"))

    # Build claim_lines from procedure codes
    claim_lines = []
    billed_amount = claim_record.get("billed_amount", 0) or 0
    line_charge = billed_amount / max(len(procedure_codes), 1)

    for code in procedure_codes:
        claim_lines.append(
            {
                "procedure_code": code,
                "line_charge": line_charge,
                "units": 1,
                "diagnosis_codes": diagnosis_codes,
            }
        )

    claim_data["claim_lines"] = claim_lines
    claim_data["diagnosis_codes"] = diagnosis_codes

    return claim_data


def parse_json_list(value: Any) -> list[str]:
    """Parse a value that may be a JSON string or list.

    Always returns a list of strings for consistency.

    Args:
        value: String, list, or None

    Returns:
        List of strings (all values converted to str)
    """
    if not value:
        return []

    if isinstance(value, list):
        # Ensure all items are strings
        return [str(item) for item in value]

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                # Convert all parsed items to strings
                return [str(item) for item in parsed]
            # Single value parsed from JSON - convert to string
            return [str(parsed)]
        except (json.JSONDecodeError, TypeError):
            return [value]

    return [str(value)]


# Backwards compatibility alias
_parse_json_list = parse_json_list
