"""Format and syntax validation rules."""

from __future__ import annotations

import re
from datetime import datetime

from backend.rules.models import RuleContext, RuleHit
from backend.utils import parse_flexible_date


def format_missing_field_rule(context: RuleContext) -> list[RuleHit]:
    """Check for missing or invalid required claim fields."""
    hits: list[RuleHit] = []
    claim = context.claim

    required_fields = [
        ("member.member_id", "Member ID"),
        ("provider.npi", "Provider NPI"),
        ("service_date", "Service Date"),
    ]

    for field_path, field_name in required_fields:
        parts = field_path.split(".")
        value = claim
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

        if not value:
            dos_alt = claim.get("dos")
            if field_path == "service_date" and dos_alt:
                continue

            hits.append(
                RuleHit(
                    rule_id="FORMAT_MISSING_FIELD",
                    description=f"Required field '{field_name}' is missing or empty",
                    weight=0.15,
                    severity="high",
                    flag="format_error",
                    citation="EDI 837 Specification",
                    metadata={"category": "format", "field": field_path},
                )
            )

    items = claim.get("items", [])
    if not items:
        hits.append(
            RuleHit(
                rule_id="FORMAT_MISSING_FIELD",
                description="Claim has no service line items",
                weight=0.20,
                severity="critical",
                flag="format_error",
                citation="EDI 837 Specification",
                metadata={"category": "format", "field": "items"},
            )
        )

    return hits


def format_invalid_date_rule(context: RuleContext) -> list[RuleHit]:
    """Validate date formats and logical date relationships."""
    hits: list[RuleHit] = []
    claim = context.claim

    service_date_str = claim.get("service_date") or claim.get("dos")
    received_date_str = claim.get("received_date")
    patient_dob_str = claim.get("member", {}).get("dob") or claim.get(
        "patient", {}
    ).get("dob")

    service_date = parse_flexible_date(service_date_str)
    received_date = parse_flexible_date(received_date_str)
    patient_dob = parse_flexible_date(patient_dob_str)
    today = datetime.now()

    if service_date_str and not service_date:
        hits.append(
            RuleHit(
                rule_id="FORMAT_INVALID_DATE",
                description=f"Invalid service date format: {service_date_str}",
                weight=0.15,
                severity="high",
                flag="format_error",
                citation="EDI 837 Specification",
                metadata={
                    "category": "format",
                    "field": "service_date",
                    "value": service_date_str,
                },
            )
        )

    if service_date and service_date > today:
        hits.append(
            RuleHit(
                rule_id="FORMAT_INVALID_DATE",
                description=f"Service date {service_date_str} is in the future",
                weight=0.18,
                severity="critical",
                flag="format_error",
                citation="EDI 837 Specification",
                metadata={
                    "category": "format",
                    "field": "service_date",
                    "value": service_date_str,
                },
            )
        )

    if service_date and received_date and service_date > received_date:
        hits.append(
            RuleHit(
                rule_id="FORMAT_INVALID_DATE",
                description=f"Service date {service_date_str} is after received date {received_date_str}",
                weight=0.15,
                severity="high",
                flag="format_error",
                citation="EDI 837 Specification",
                metadata={"category": "format", "field": "service_date"},
            )
        )

    if service_date and patient_dob and service_date < patient_dob:
        hits.append(
            RuleHit(
                rule_id="FORMAT_INVALID_DATE",
                description=f"Service date {service_date_str} is before patient birth date",
                weight=0.20,
                severity="critical",
                flag="format_error",
                citation="EDI 837 Specification",
                metadata={"category": "format", "field": "service_date"},
            )
        )

    return hits


def format_invalid_code_rule(context: RuleContext) -> list[RuleHit]:
    """Validate ICD-10 and CPT/HCPCS code formats."""
    hits: list[RuleHit] = []
    valid_codes = context.datasets.get("valid_codes", {})
    cpt_codes = valid_codes.get("cpt", set())
    icd10_codes = valid_codes.get("icd10", set())

    icd10_pattern = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")
    cpt_pattern = re.compile(r"^\d{5}$")
    hcpcs_pattern = re.compile(r"^[A-Z]\d{4}$")

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code", "")

        if not code:
            hits.append(
                RuleHit(
                    rule_id="FORMAT_INVALID_CODE",
                    description=f"Line {idx + 1} missing procedure code",
                    weight=0.15,
                    severity="high",
                    flag="format_error",
                    citation="EDI 837 Specification",
                    metadata={
                        "category": "format",
                        "line_index": idx,
                        "field": "procedure_code",
                    },
                )
            )
            continue

        is_valid_format = (
            cpt_pattern.match(code)
            or hcpcs_pattern.match(code)
            or code.startswith("99")
        )

        if not is_valid_format:
            hits.append(
                RuleHit(
                    rule_id="FORMAT_INVALID_CODE",
                    description=f"Invalid procedure code format: {code}",
                    weight=0.12,
                    severity="medium",
                    flag="format_error",
                    citation="AMA CPT / CMS HCPCS",
                    metadata={"category": "format", "line_index": idx, "code": code},
                )
            )

        if cpt_codes and cpt_pattern.match(code) and code not in cpt_codes:
            hits.append(
                RuleHit(
                    rule_id="FORMAT_INVALID_CODE",
                    description=f"CPT code {code} not found in valid code set",
                    weight=0.14,
                    severity="high",
                    flag="format_error",
                    citation="AMA CPT",
                    metadata={"category": "format", "line_index": idx, "code": code},
                )
            )

    for dx_code in context.claim.get("diagnosis_codes", []):
        if not dx_code:
            continue

        if not icd10_pattern.match(dx_code):
            hits.append(
                RuleHit(
                    rule_id="FORMAT_INVALID_CODE",
                    description=f"Invalid ICD-10 code format: {dx_code}",
                    weight=0.12,
                    severity="medium",
                    flag="format_error",
                    citation="CMS ICD-10-CM",
                    metadata={
                        "category": "format",
                        "code": dx_code,
                        "code_type": "ICD-10",
                    },
                )
            )

        if icd10_codes and dx_code not in icd10_codes:
            hits.append(
                RuleHit(
                    rule_id="FORMAT_INVALID_CODE",
                    description=f"ICD-10 code {dx_code} not found in valid code set",
                    weight=0.14,
                    severity="high",
                    flag="format_error",
                    citation="CMS ICD-10-CM",
                    metadata={
                        "category": "format",
                        "code": dx_code,
                        "code_type": "ICD-10",
                    },
                )
            )

    return hits
