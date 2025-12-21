"""Financial and billing amount rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit


def high_dollar_rule(context: RuleContext) -> list[RuleHit]:
    """Flag claims exceeding high-dollar thresholds."""
    tiers = context.config.get("high_dollar_tiers", [(10000, 0.1), (25000, 0.15)])
    total_billed = sum(
        item.get("line_amount", 0) for item in context.claim.get("items", [])
    )
    hits: list[RuleHit] = []
    for threshold, weight in sorted(tiers):
        if total_billed >= threshold:
            hits.append(
                RuleHit(
                    rule_id=f"HIGH_DOLLAR_{threshold}",
                    description=f"Total billed amount ${total_billed:,.2f} exceeds threshold ${threshold:,.2f}",
                    weight=weight,
                    severity="high",
                    flag="high_dollar",
                    metadata={
                        "category": "financial",
                        "threshold": threshold,
                        "total_billed": total_billed,
                    },
                )
            )
    return hits


def reimbursement_outlier_rule(context: RuleContext) -> list[RuleHit]:
    """Flag line items exceeding MPFS benchmark by configured percentile."""
    mpfs: dict[str, dict[str, dict[str, float]]] = context.datasets.get("mpfs", {})
    region = context.claim.get("provider", {}).get("region", "national")
    percentile = context.config.get("outlier_percentile", 0.95)
    hits: list[RuleHit] = []
    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        line_amount = item.get("line_amount", 0)
        benchmark = None
        if code and code in mpfs:
            regions = mpfs[code].get("regions", {})
            benchmark = regions.get(region) or regions.get("national")
        if benchmark and line_amount >= benchmark * (1 + percentile):
            estimated_delta = line_amount - benchmark
            hits.append(
                RuleHit(
                    rule_id="REIMB_OUTLIER",
                    description=f"{code} billed ${line_amount:,.2f} vs benchmark ${benchmark:,.2f}",
                    weight=0.12,
                    severity="medium",
                    flag="reimbursement_outlier",
                    citation="CMS MPFS",
                    metadata={
                        "category": "financial",
                        "line_index": idx,
                        "benchmark": benchmark,
                        "percentile": percentile,
                        "estimated_roi": estimated_delta,
                    },
                )
            )
    return hits


def misc_code_rule(context: RuleContext) -> list[RuleHit]:
    """Flag unlisted/miscellaneous procedure codes.

    Unlisted codes end in 99 within their series (e.g., 47999, 64999)
    and require additional documentation. Note: 99XXX E/M codes are
    NOT miscellaneous - they are standard Evaluation & Management codes.
    """
    # Known unlisted procedure codes that require documentation
    UNLISTED_CODES = {
        "99199",  # Unlisted special service
        "99499",  # Unlisted E/M service
        "17999",  # Unlisted procedure, skin
        "19499",  # Unlisted procedure, breast
        "20999",  # Unlisted procedure, musculoskeletal
        "21499",  # Unlisted musculoskeletal procedure, head
        "22899",  # Unlisted procedure, spine
        "27299",  # Unlisted procedure, pelvis/hip
        "27599",  # Unlisted procedure, femur/knee
        "27899",  # Unlisted procedure, leg/ankle
        "28899",  # Unlisted procedure, foot/toes
        "29799",  # Unlisted procedure, casting/strapping
        "29999",  # Unlisted procedure, arthroscopy
        "36299",  # Unlisted procedure, vascular injection
        "36899",  # Unlisted procedure, vascular
        "37799",  # Unlisted vascular endoscopy
        "43499",  # Unlisted procedure, esophagus
        "44799",  # Unlisted laparoscopy, intestine
        "47999",  # Unlisted procedure, biliary tract
        "49999",  # Unlisted procedure, abdomen
        "55899",  # Unlisted procedure, male genital
        "58999",  # Unlisted procedure, female genital
        "59899",  # Unlisted procedure, maternity
        "64999",  # Unlisted procedure, nervous system
        "69799",  # Unlisted procedure, middle ear
        "76999",  # Unlisted US procedure
        "78999",  # Unlisted nuclear medicine
        "79999",  # Unlisted radiopharmaceutical
    }

    hits: list[RuleHit] = []
    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code", "")
        # Check if code is an unlisted procedure code
        if code in UNLISTED_CODES or (
            len(code) == 5 and code.endswith("99") and not code.startswith("99")
        ):
            hits.append(
                RuleHit(
                    rule_id="MISC_CODE",
                    description=f"Procedure {code} is an unlisted code requiring documentation",
                    weight=0.05,
                    severity="low",
                    flag="misc_code",
                    metadata={"category": "financial", "line_index": idx},
                )
            )
    return hits
