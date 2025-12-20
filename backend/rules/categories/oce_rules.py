"""Outpatient Code Editor (OCE) rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit


def oce_revenue_code_rule(context: RuleContext) -> list[RuleHit]:
    """Check for invalid revenue code combinations."""
    revenue_combinations = context.datasets.get("oce_revenue_combinations", {})
    hits: list[RuleHit] = []

    items = context.claim.get("items", [])
    revenue_codes = [(idx, item.get("revenue_code")) for idx, item in enumerate(items) if item.get("revenue_code")]

    for idx, rev_code in revenue_codes:
        if rev_code not in revenue_combinations:
            continue

        rules = revenue_combinations[rev_code]
        required_with = rules.get("required_with", [])
        mutually_exclusive = rules.get("mutually_exclusive", [])
        all_revenue_codes = {rc for _, rc in revenue_codes}

        if required_with and not all_revenue_codes.intersection(set(required_with)):
            hits.append(
                RuleHit(
                    rule_id="OCE_REVENUE_CODE_INVALID",
                    description=f"Revenue code {rev_code} requires one of: {', '.join(required_with)}",
                    weight=0.12,
                    severity="medium",
                    flag="oce_revenue_invalid",
                    citation="CMS OCE",
                    metadata={
                        "category": "oce",
                        "line_index": idx,
                        "revenue_code": rev_code,
                        "required_with": required_with,
                    },
                )
            )

        conflicts = all_revenue_codes.intersection(set(mutually_exclusive))
        if conflicts:
            hits.append(
                RuleHit(
                    rule_id="OCE_REVENUE_CODE_CONFLICT",
                    description=f"Revenue code {rev_code} conflicts with: {', '.join(conflicts)}",
                    weight=0.14,
                    severity="high",
                    flag="oce_revenue_conflict",
                    citation="CMS OCE",
                    metadata={
                        "category": "oce",
                        "line_index": idx,
                        "revenue_code": rev_code,
                        "conflicting_codes": list(conflicts),
                    },
                )
            )

    return hits


def oce_inpatient_only_rule(context: RuleContext) -> list[RuleHit]:
    """Check for inpatient-only procedures in outpatient setting."""
    inpatient_only = context.datasets.get("inpatient_only_codes", set())
    claim = context.claim
    claim_type = claim.get("claim_type", "").lower()
    pos = claim.get("place_of_service")

    outpatient_pos = {"11", "12", "19", "20", "22", "24", "49", "50", "71", "72"}
    is_outpatient = claim_type == "outpatient" or pos in outpatient_pos

    if not is_outpatient:
        return []

    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code")
        if code and code in inpatient_only:
            hits.append(
                RuleHit(
                    rule_id="OCE_INPATIENT_ONLY",
                    description=f"Procedure {code} is inpatient-only but billed in outpatient setting",
                    weight=0.18,
                    severity="critical",
                    flag="oce_inpatient_only",
                    citation="CMS OCE Inpatient-Only List",
                    metadata={
                        "category": "oce",
                        "line_index": idx,
                        "procedure_code": code,
                        "place_of_service": pos,
                        "claim_type": claim_type,
                    },
                )
            )

    return hits


def oce_observation_hours_rule(context: RuleContext) -> list[RuleHit]:
    """Check if observation hours exceed limits."""
    claim = context.claim
    observation_hours = claim.get("observation_hours")
    max_observation_hours = context.config.get("max_observation_hours", 48)
    extended_observation_threshold = context.config.get("extended_observation_threshold", 24)

    if observation_hours is None:
        for item in claim.get("items", []):
            if item.get("revenue_code") in {"0760", "0762"}:
                observation_hours = item.get("quantity") or item.get("units")
                break

    if observation_hours is None:
        return []

    hits: list[RuleHit] = []

    if observation_hours > max_observation_hours:
        hits.append(
            RuleHit(
                rule_id="OCE_OBSERVATION_EXCESSIVE",
                description=f"Observation hours {observation_hours} exceeds maximum {max_observation_hours}",
                weight=0.16,
                severity="high",
                flag="oce_observation_excessive",
                citation="CMS Observation Services Policy",
                metadata={
                    "category": "oce",
                    "observation_hours": observation_hours,
                    "max_hours": max_observation_hours,
                },
            )
        )
    elif observation_hours > extended_observation_threshold:
        medical_necessity_doc = claim.get("observation_necessity_documented", False)
        if not medical_necessity_doc:
            hits.append(
                RuleHit(
                    rule_id="OCE_OBSERVATION_EXTENDED",
                    description=f"Extended observation ({observation_hours}h) requires medical necessity documentation",
                    weight=0.10,
                    severity="medium",
                    flag="oce_observation_extended",
                    citation="CMS Observation Services Policy",
                    metadata={
                        "category": "oce",
                        "observation_hours": observation_hours,
                        "threshold": extended_observation_threshold,
                    },
                )
            )

    return hits
