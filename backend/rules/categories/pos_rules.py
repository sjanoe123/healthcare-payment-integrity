"""Place of Service (POS) rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit


def pos_invalid_rule(context: RuleContext) -> list[RuleHit]:
    """Check for invalid place of service for the procedure."""
    pos_restrictions = context.datasets.get("pos_restrictions", {})
    valid_pos_codes = context.datasets.get("valid_pos_codes", set())
    hits: list[RuleHit] = []

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        pos = item.get("place_of_service") or context.claim.get("place_of_service")

        if not pos:
            continue

        if valid_pos_codes and pos not in valid_pos_codes:
            hits.append(
                RuleHit(
                    rule_id="POS_INVALID",
                    rule_type="coverage",
                    description=f"Invalid place of service code: {pos}",
                    weight=0.12,
                    severity="medium",
                    flag="pos_invalid",
                    citation="CMS Place of Service Codes",
                    metadata={
                        "category": "pos",
                        "line_index": idx,
                        "place_of_service": pos,
                    },
                )
            )
            continue

        if not code or code not in pos_restrictions:
            continue

        restrictions = pos_restrictions[code]
        allowed_pos = restrictions.get("allowed_pos", [])
        excluded_pos = restrictions.get("excluded_pos", [])

        if allowed_pos and pos not in allowed_pos:
            hits.append(
                RuleHit(
                    rule_id="POS_INVALID",
                    rule_type="coverage",
                    description=f"Procedure {code} not allowed in place of service {pos}",
                    weight=0.14,
                    severity="high",
                    flag="pos_invalid",
                    citation="CMS Place of Service Policy",
                    metadata={
                        "category": "pos",
                        "line_index": idx,
                        "procedure_code": code,
                        "place_of_service": pos,
                        "allowed_pos": allowed_pos,
                    },
                )
            )

        if pos in excluded_pos:
            hits.append(
                RuleHit(
                    rule_id="POS_INVALID",
                    rule_type="coverage",
                    description=f"Procedure {code} explicitly excluded from place of service {pos}",
                    weight=0.16,
                    severity="high",
                    flag="pos_invalid",
                    citation="CMS Place of Service Policy",
                    metadata={
                        "category": "pos",
                        "line_index": idx,
                        "procedure_code": code,
                        "place_of_service": pos,
                    },
                )
            )

    return hits


def pos_provider_mismatch_rule(context: RuleContext) -> list[RuleHit]:
    """Check for mismatch between place of service and provider type."""
    provider_pos_rules = context.datasets.get("provider_pos_rules", {})
    claim = context.claim
    provider = claim.get("provider", {})
    provider_type = provider.get("provider_type") or provider.get("specialty")
    claim_pos = claim.get("place_of_service")

    if not provider_type or not claim_pos:
        return []

    provider_rules = provider_pos_rules.get(provider_type)
    if not provider_rules:
        return []

    hits: list[RuleHit] = []

    facility_pos = {
        "21",
        "22",
        "23",
        "24",
        "31",
        "32",
        "33",
        "34",
        "51",
        "52",
        "53",
        "54",
        "55",
        "56",
        "61",
    }
    non_facility_pos = {"11", "12", "17", "19", "20", "49", "50", "71", "72"}

    is_facility_provider = provider_rules.get("is_facility", False)
    is_non_facility_provider = provider_rules.get("is_non_facility", False)

    if is_non_facility_provider and claim_pos in facility_pos:
        hits.append(
            RuleHit(
                rule_id="POS_PROVIDER_MISMATCH",
                rule_type="coverage",
                description=f"Non-facility provider type {provider_type} billing with facility POS {claim_pos}",
                weight=0.13,
                severity="high",
                flag="pos_provider_mismatch",
                citation="CMS Provider Enrollment",
                metadata={
                    "category": "pos",
                    "provider_type": provider_type,
                    "place_of_service": claim_pos,
                    "expected_pos_type": "non-facility",
                },
            )
        )

    if is_facility_provider and claim_pos in non_facility_pos:
        hits.append(
            RuleHit(
                rule_id="POS_PROVIDER_MISMATCH",
                rule_type="coverage",
                description=f"Facility provider type {provider_type} billing with non-facility POS {claim_pos}",
                weight=0.13,
                severity="high",
                flag="pos_provider_mismatch",
                citation="CMS Provider Enrollment",
                metadata={
                    "category": "pos",
                    "provider_type": provider_type,
                    "place_of_service": claim_pos,
                    "expected_pos_type": "facility",
                },
            )
        )

    allowed_pos = provider_rules.get("allowed_pos", [])
    if allowed_pos and claim_pos not in allowed_pos:
        hits.append(
            RuleHit(
                rule_id="POS_PROVIDER_MISMATCH",
                rule_type="coverage",
                description=f"Provider type {provider_type} not authorized for POS {claim_pos}",
                weight=0.12,
                severity="medium",
                flag="pos_provider_mismatch",
                citation="CMS Provider Enrollment",
                metadata={
                    "category": "pos",
                    "provider_type": provider_type,
                    "place_of_service": claim_pos,
                    "allowed_pos": allowed_pos,
                },
            )
        )

    return hits
