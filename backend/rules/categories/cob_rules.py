"""Coordination of Benefits (COB) rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit


def cob_wrong_primary_rule(context: RuleContext) -> list[RuleHit]:
    """Check if claim is submitted to wrong primary payer."""
    claim = context.claim
    cob_info = claim.get("cob", {}) or claim.get("coordination_of_benefits", {})
    payer_id = claim.get("payer_id")

    if not cob_info:
        return []

    other_payers = cob_info.get("other_payers", [])
    claim_payer_priority = cob_info.get("this_payer_priority", 1)

    for other_payer in other_payers:
        other_priority = other_payer.get("priority", 2)
        other_payer_id = other_payer.get("payer_id")

        if other_priority < claim_payer_priority:
            return [
                RuleHit(
                    rule_id="COB_WRONG_PRIMARY",
                    description=f"Claim submitted as primary but payer {other_payer_id} has higher priority",
                    weight=0.16,
                    severity="high",
                    flag="cob_wrong_primary",
                    citation="CMS Coordination of Benefits",
                    metadata={
                        "category": "cob",
                        "this_payer_id": payer_id,
                        "this_payer_priority": claim_payer_priority,
                        "primary_payer_id": other_payer_id,
                        "primary_payer_priority": other_priority,
                    },
                )
            ]

    return []


def cob_incomplete_rule(context: RuleContext) -> list[RuleHit]:
    """Check if COB information is incomplete when multiple payers exist."""
    claim = context.claim
    cob_info = claim.get("cob", {}) or claim.get("coordination_of_benefits", {})

    has_other_coverage = claim.get("has_other_coverage", False)
    member = claim.get("member", {})
    has_medicare = member.get("has_medicare", False)

    hits: list[RuleHit] = []

    if has_other_coverage and not cob_info:
        hits.append(
            RuleHit(
                rule_id="COB_INCOMPLETE",
                description="Other coverage indicated but no COB information provided",
                weight=0.12,
                severity="medium",
                flag="cob_incomplete",
                citation="CMS Coordination of Benefits",
                metadata={
                    "category": "cob",
                    "issue": "missing_cob_info",
                },
            )
        )

    if has_medicare and not cob_info.get("medicare_info"):
        hits.append(
            RuleHit(
                rule_id="COB_INCOMPLETE",
                description="Member has Medicare but Medicare COB details not provided",
                weight=0.14,
                severity="high",
                flag="cob_incomplete",
                citation="CMS Medicare Secondary Payer",
                metadata={
                    "category": "cob",
                    "issue": "missing_medicare_cob",
                },
            )
        )

    other_payers = cob_info.get("other_payers", [])
    for idx, payer in enumerate(other_payers):
        required_fields = ["payer_id", "priority"]
        missing = [f for f in required_fields if not payer.get(f)]
        if missing:
            hits.append(
                RuleHit(
                    rule_id="COB_INCOMPLETE",
                    description=f"Other payer {idx + 1} missing required fields: {', '.join(missing)}",
                    weight=0.10,
                    severity="medium",
                    flag="cob_incomplete",
                    citation="CMS Coordination of Benefits",
                    metadata={
                        "category": "cob",
                        "payer_index": idx,
                        "missing_fields": missing,
                    },
                )
            )

    return hits
