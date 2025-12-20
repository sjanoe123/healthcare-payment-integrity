"""Eligibility and coverage rules."""

from __future__ import annotations

from datetime import datetime

from backend.rules.models import RuleContext, RuleHit


def eligibility_inactive_rule(context: RuleContext) -> list[RuleHit]:
    """Check if member was eligible on date of service."""
    member_eligibility = context.datasets.get("member_eligibility", {})
    claim = context.claim
    member_id = claim.get("member", {}).get("member_id")
    service_date_str = claim.get("service_date") or claim.get("dos")

    if not member_id or not service_date_str:
        return []

    # Only check eligibility if we have eligibility data loaded
    # Skip rule if eligibility dataset is empty (not configured)
    if not member_eligibility:
        return []

    eligibility = member_eligibility.get(member_id)
    if not eligibility:
        return [
            RuleHit(
                rule_id="ELIGIBILITY_INACTIVE",
                description=f"Member {member_id} not found in eligibility database",
                weight=0.22,
                severity="critical",
                flag="eligibility_inactive",
                citation="Payer Eligibility Policy",
                metadata={"category": "eligibility", "member_id": member_id},
            )
        ]

    def parse_date(date_str: str) -> datetime | None:
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    service_date = parse_date(service_date_str)
    eff_date = parse_date(eligibility.get("effective_date", ""))
    term_date = parse_date(eligibility.get("termination_date", ""))

    if not service_date:
        return []

    if eff_date and service_date < eff_date:
        return [
            RuleHit(
                rule_id="ELIGIBILITY_INACTIVE",
                description=f"Service date {service_date_str} is before member effective date",
                weight=0.22,
                severity="critical",
                flag="eligibility_inactive",
                citation="Payer Eligibility Policy",
                metadata={
                    "category": "eligibility",
                    "member_id": member_id,
                    "effective_date": eligibility.get("effective_date"),
                },
            )
        ]

    if term_date and service_date > term_date:
        return [
            RuleHit(
                rule_id="ELIGIBILITY_INACTIVE",
                description=f"Service date {service_date_str} is after member termination date",
                weight=0.22,
                severity="critical",
                flag="eligibility_inactive",
                citation="Payer Eligibility Policy",
                metadata={
                    "category": "eligibility",
                    "member_id": member_id,
                    "termination_date": eligibility.get("termination_date"),
                },
            )
        ]

    return []


def eligibility_non_covered_rule(context: RuleContext) -> list[RuleHit]:
    """Check if services are covered under member's benefit plan."""
    benefit_exclusions = context.datasets.get("benefit_exclusions", {})
    claim = context.claim
    plan_id = claim.get("member", {}).get("plan_id")

    if not plan_id:
        return []

    plan_exclusions = benefit_exclusions.get(plan_id, set())
    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code")
        if code and code in plan_exclusions:
            hits.append(
                RuleHit(
                    rule_id="ELIGIBILITY_NON_COVERED",
                    description=f"Procedure {code} is excluded from member's benefit plan",
                    weight=0.18,
                    severity="high",
                    flag="eligibility_non_covered",
                    citation="Member Benefit Plan",
                    metadata={
                        "category": "eligibility",
                        "line_index": idx,
                        "plan_id": plan_id,
                        "procedure_code": code,
                    },
                )
            )

    return hits


def eligibility_benefit_limit_rule(context: RuleContext) -> list[RuleHit]:
    """Check if service exceeds annual or lifetime benefit limits."""
    benefit_limits = context.datasets.get("benefit_limits", {})
    benefit_utilization = context.datasets.get("benefit_utilization", {})
    claim = context.claim
    member_id = claim.get("member", {}).get("member_id")
    plan_id = claim.get("member", {}).get("plan_id")

    if not member_id or not plan_id:
        return []

    plan_limits = benefit_limits.get(plan_id, {})
    member_usage = benefit_utilization.get(member_id, {})
    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code")
        quantity = item.get("quantity", 1)
        amount = item.get("line_amount", 0)

        if not code:
            continue

        limit_info = plan_limits.get(code)
        if not limit_info:
            continue

        current_usage = member_usage.get(code, {"units": 0, "amount": 0})

        if "max_units" in limit_info:
            max_units = limit_info["max_units"]
            used_units = current_usage.get("units", 0)
            if used_units + quantity > max_units:
                hits.append(
                    RuleHit(
                        rule_id="ELIGIBILITY_LIMIT_EXCEEDED",
                        description=f"Procedure {code}: {used_units + quantity} units exceeds limit of {max_units}",
                        weight=0.15,
                        severity="high",
                        flag="eligibility_limit",
                        citation="Member Benefit Plan",
                        metadata={
                            "category": "eligibility",
                            "line_index": idx,
                            "limit_type": "units",
                            "limit": max_units,
                            "used": used_units,
                            "requested": quantity,
                        },
                    )
                )

        if "max_amount" in limit_info:
            max_amount = limit_info["max_amount"]
            used_amount = current_usage.get("amount", 0)
            if used_amount + amount > max_amount:
                hits.append(
                    RuleHit(
                        rule_id="ELIGIBILITY_LIMIT_EXCEEDED",
                        description=f"Procedure {code}: ${used_amount + amount:.2f} exceeds limit of ${max_amount:.2f}",
                        weight=0.15,
                        severity="high",
                        flag="eligibility_limit",
                        citation="Member Benefit Plan",
                        metadata={
                            "category": "eligibility",
                            "line_index": idx,
                            "limit_type": "amount",
                            "limit": max_amount,
                            "used": used_amount,
                            "requested": amount,
                        },
                    )
                )

    return hits


def eligibility_no_auth_rule(context: RuleContext) -> list[RuleHit]:
    """Check if prior authorization is required but missing."""
    auth_required = context.datasets.get("auth_required_codes", set())
    authorizations = context.datasets.get("authorizations", {})
    claim = context.claim
    member_id = claim.get("member", {}).get("member_id")

    if not member_id:
        return []

    member_auths = authorizations.get(member_id, {})
    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code")
        if not code or code not in auth_required:
            continue

        auth = member_auths.get(code)
        if not auth:
            hits.append(
                RuleHit(
                    rule_id="ELIGIBILITY_NO_AUTH",
                    description=f"Procedure {code} requires prior authorization but none found",
                    weight=0.16,
                    severity="high",
                    flag="eligibility_no_auth",
                    citation="Payer Prior Authorization Policy",
                    metadata={
                        "category": "eligibility",
                        "line_index": idx,
                        "procedure_code": code,
                    },
                )
            )
            continue

        auth_status = auth.get("status", "").lower()
        if auth_status not in ["approved", "active"]:
            hits.append(
                RuleHit(
                    rule_id="ELIGIBILITY_NO_AUTH",
                    description=f"Prior authorization for {code} has status: {auth_status}",
                    weight=0.16,
                    severity="high",
                    flag="eligibility_no_auth",
                    citation="Payer Prior Authorization Policy",
                    metadata={
                        "category": "eligibility",
                        "line_index": idx,
                        "procedure_code": code,
                        "auth_status": auth_status,
                    },
                )
            )

    return hits
