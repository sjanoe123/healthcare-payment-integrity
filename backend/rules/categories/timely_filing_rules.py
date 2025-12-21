"""Timely filing rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit
from backend.utils import parse_flexible_date


def timely_filing_late_rule(context: RuleContext) -> list[RuleHit]:
    """Check if claim was submitted within the filing deadline."""
    claim = context.claim
    service_date_str = claim.get("service_date") or claim.get("dos")
    received_date_str = claim.get("received_date")

    filing_limit_days = context.config.get("filing_limit_days", 365)

    if not service_date_str or not received_date_str:
        return []

    service_date = parse_flexible_date(service_date_str)
    received_date = parse_flexible_date(received_date_str)

    if not service_date or not received_date:
        return []

    days_elapsed = (received_date - service_date).days

    if days_elapsed > filing_limit_days:
        return [
            RuleHit(
                rule_id="TIMELY_FILING_LATE",
                description=f"Claim filed {days_elapsed} days after service, exceeds {filing_limit_days}-day limit",
                weight=0.22,
                severity="critical",
                flag="timely_filing_late",
                citation="Payer Timely Filing Policy",
                metadata={
                    "category": "timely_filing",
                    "days_elapsed": days_elapsed,
                    "filing_limit": filing_limit_days,
                    "service_date": service_date_str,
                    "received_date": received_date_str,
                },
            )
        ]

    if days_elapsed > filing_limit_days * 0.9:
        return [
            RuleHit(
                rule_id="TIMELY_FILING_WARNING",
                description=f"Claim filed {days_elapsed} days after service, approaching {filing_limit_days}-day limit",
                weight=0.05,
                severity="low",
                flag="timely_filing_warning",
                citation="Payer Timely Filing Policy",
                metadata={
                    "category": "timely_filing",
                    "days_elapsed": days_elapsed,
                    "filing_limit": filing_limit_days,
                },
            )
        ]

    return []


def timely_filing_no_exception_rule(context: RuleContext) -> list[RuleHit]:
    """Check if late submission has a valid exception documented."""
    claim = context.claim
    service_date_str = claim.get("service_date") or claim.get("dos")
    received_date_str = claim.get("received_date")
    exception_code = claim.get("timely_filing_exception")

    filing_limit_days = context.config.get("filing_limit_days", 365)
    valid_exceptions = context.config.get(
        "timely_filing_exceptions",
        [
            "cob_delay",
            "retroactive_eligibility",
            "provider_appeal",
            "system_error",
        ],
    )

    if not service_date_str or not received_date_str:
        return []

    service_date = parse_flexible_date(service_date_str)
    received_date = parse_flexible_date(received_date_str)

    if not service_date or not received_date:
        return []

    days_elapsed = (received_date - service_date).days

    if days_elapsed <= filing_limit_days:
        return []

    if not exception_code:
        return [
            RuleHit(
                rule_id="TIMELY_FILING_NO_EXCEPTION",
                description=f"Late filing ({days_elapsed} days) without documented exception",
                weight=0.20,
                severity="critical",
                flag="timely_filing_no_exception",
                citation="Payer Timely Filing Policy",
                metadata={
                    "category": "timely_filing",
                    "days_elapsed": days_elapsed,
                    "valid_exceptions": valid_exceptions,
                },
            )
        ]

    if exception_code not in valid_exceptions:
        return [
            RuleHit(
                rule_id="TIMELY_FILING_INVALID_EXCEPTION",
                description=f"Late filing exception code '{exception_code}' is not valid",
                weight=0.18,
                severity="high",
                flag="timely_filing_invalid_exception",
                citation="Payer Timely Filing Policy",
                metadata={
                    "category": "timely_filing",
                    "exception_code": exception_code,
                    "valid_exceptions": valid_exceptions,
                },
            )
        ]

    return []
