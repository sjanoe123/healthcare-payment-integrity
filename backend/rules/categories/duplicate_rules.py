"""Duplicate claim detection rules."""

from __future__ import annotations

from collections import Counter

from backend.rules.models import RuleContext, RuleHit


def duplicate_line_rule(context: RuleContext) -> list[RuleHit]:
    """Detect duplicate procedure codes on the same claim."""
    items = context.claim.get("items", [])
    counter = Counter(
        (item.get("procedure_code"), item.get("modifier")) for item in items
    )
    hits: list[RuleHit] = []
    for (code, modifier), count in counter.items():
        if code and count > 1:
            hits.append(
                RuleHit(
                    rule_id="DUPLICATE_LINE",
                    rule_type="financial",
                    description=f"Procedure {code} repeated {count} times",
                    weight=0.08,
                    severity="medium",
                    flag="duplicate_line",
                    metadata={
                        "category": "financial",
                        "modifier": modifier,
                        "count": count,
                    },
                )
            )
    return hits


def duplicate_exact_rule(context: RuleContext) -> list[RuleHit]:
    """Detect exact duplicate claims (same provider, member, service, date, amount)."""
    claim_history = context.datasets.get("claim_history", {})
    claim = context.claim

    claim_signature = (
        claim.get("member", {}).get("member_id"),
        claim.get("provider", {}).get("npi"),
        claim.get("service_date") or claim.get("dos"),
        tuple(
            sorted(item.get("procedure_code", "") for item in claim.get("items", []))
        ),
    )

    if claim_signature in claim_history:
        original_claim_id = claim_history[claim_signature]
        return [
            RuleHit(
                rule_id="DUPLICATE_EXACT",
                rule_type="financial",
                description=f"Exact duplicate of previously submitted claim {original_claim_id}",
                weight=0.20,
                severity="critical",
                flag="duplicate_exact",
                citation="Payer Duplicate Claims Policy",
                metadata={
                    "category": "duplicate",
                    "original_claim_id": original_claim_id,
                },
            )
        ]
    return []


def duplicate_same_day_rule(context: RuleContext) -> list[RuleHit]:
    """Detect same-service same-day duplicates without modifier."""
    items = context.claim.get("items", [])
    dos = context.claim.get("service_date") or context.claim.get("dos")

    code_occurrences: dict[str, list[int]] = {}
    for idx, item in enumerate(items):
        code = item.get("procedure_code")
        modifier = item.get("modifier")
        if code and not modifier:
            if code not in code_occurrences:
                code_occurrences[code] = []
            code_occurrences[code].append(idx)

    hits: list[RuleHit] = []
    for code, indices in code_occurrences.items():
        if len(indices) > 1:
            hits.append(
                RuleHit(
                    rule_id="DUPLICATE_SAME_DAY",
                    rule_type="financial",
                    description=f"Same-day same-service duplicate: {code} on {dos} without modifier",
                    weight=0.12,
                    severity="high",
                    flag="duplicate_same_day",
                    citation="CMS Billing Guidelines",
                    metadata={
                        "category": "duplicate",
                        "line_indexes": indices,
                        "service_date": dos,
                    },
                )
            )
    return hits


def duplicate_cross_claim_rule(context: RuleContext) -> list[RuleHit]:
    """Detect services billed on separate claims for the same date."""
    cross_claim_history = context.datasets.get("cross_claim_history", {})
    claim = context.claim
    member_id = claim.get("member", {}).get("member_id")
    dos = claim.get("service_date") or claim.get("dos")
    npi = claim.get("provider", {}).get("npi")

    if not all([member_id, dos, npi]):
        return []

    lookup_key = (member_id, dos, npi)
    if lookup_key not in cross_claim_history:
        return []

    previous_claims = cross_claim_history[lookup_key]
    current_codes = {
        item.get("procedure_code")
        for item in claim.get("items", [])
        if item.get("procedure_code")
    }

    hits: list[RuleHit] = []
    for prev_claim_id, prev_codes in previous_claims.items():
        overlapping = current_codes.intersection(prev_codes)
        if overlapping:
            hits.append(
                RuleHit(
                    rule_id="DUPLICATE_CROSS_CLAIM",
                    rule_type="financial",
                    description=f"Services {', '.join(overlapping)} already billed on claim {prev_claim_id}",
                    weight=0.15,
                    severity="high",
                    flag="duplicate_cross_claim",
                    citation="Payer Duplicate Claims Policy",
                    metadata={
                        "category": "duplicate",
                        "original_claim_id": prev_claim_id,
                        "overlapping_codes": list(overlapping),
                    },
                )
            )
    return hits
