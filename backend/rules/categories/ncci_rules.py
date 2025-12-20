"""NCCI (National Correct Coding Initiative) rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit


def ncci_ptp_rule(context: RuleContext) -> list[RuleHit]:
    """Check for NCCI Procedure-to-Procedure (PTP) edit violations."""
    dataset = context.datasets.get("ncci_ptp", {})
    codes = [item.get("procedure_code") for item in context.claim.get("items", [])]
    hits: list[RuleHit] = []
    for i, code_a in enumerate(codes):
        if not code_a:
            continue
        for j, code_b in enumerate(codes):
            if j <= i or not code_b:
                continue
            key = tuple(sorted((code_a, code_b)))
            if key in dataset:
                rationale = dataset[key]
                hits.append(
                    RuleHit(
                        rule_id="NCCI_PTP",
                        description=f"PTP edit between {code_a} and {code_b}",
                        weight=0.18,
                        severity="critical",
                        flag="ncci_ptp",
                        citation=rationale.get("citation"),
                        metadata={
                            "category": "ncci",
                            "line_indexes": [i, j],
                            "modifier": rationale.get("modifier"),
                        },
                    )
                )
    return hits


def ncci_mue_rule(context: RuleContext) -> list[RuleHit]:
    """Check for NCCI Medically Unlikely Edit (MUE) violations."""
    dataset = context.datasets.get("ncci_mue", {})
    hits: list[RuleHit] = []
    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        quantity = item.get("quantity") or 0
        entry = dataset.get(code)
        limit = entry.get("limit") if isinstance(entry, dict) else entry
        if limit is not None and quantity > limit:
            hits.append(
                RuleHit(
                    rule_id="NCCI_MUE",
                    description=f"Quantity {quantity} exceeds MUE limit {limit} for {code}",
                    weight=0.16,
                    severity="high",
                    flag="ncci_mue",
                    citation="CMS NCCI MUE",
                    metadata={
                        "category": "ncci",
                        "line_index": idx,
                        "limit": limit,
                    },
                )
            )
    return hits


def ncci_addon_no_primary_rule(context: RuleContext) -> list[RuleHit]:
    """Check for add-on codes billed without their primary procedure."""
    addon_codes = context.datasets.get("ncci_addon", {})
    if not addon_codes:
        return []

    items = context.claim.get("items", [])
    codes_present = {item.get("procedure_code") for item in items if item.get("procedure_code")}
    hits: list[RuleHit] = []

    for idx, item in enumerate(items):
        code = item.get("procedure_code")
        if not code or code not in addon_codes:
            continue

        primary_codes = addon_codes[code].get("primary_codes", [])
        if primary_codes and not codes_present.intersection(set(primary_codes)):
            hits.append(
                RuleHit(
                    rule_id="NCCI_ADDON_NO_PRIMARY",
                    description=f"Add-on code {code} billed without required primary procedure",
                    weight=0.15,
                    severity="high",
                    flag="ncci_addon_no_primary",
                    citation="CMS NCCI Add-on Code Edits",
                    metadata={
                        "category": "ncci",
                        "line_index": idx,
                        "required_primary_codes": primary_codes[:5],
                    },
                )
            )
    return hits


def ncci_mutually_exclusive_rule(context: RuleContext) -> list[RuleHit]:
    """Check for mutually exclusive procedure codes billed together."""
    mutex_pairs = context.datasets.get("ncci_mutex", {})
    if not mutex_pairs:
        return []

    items = context.claim.get("items", [])
    codes = [(idx, item.get("procedure_code")) for idx, item in enumerate(items)]
    hits: list[RuleHit] = []

    for i, (idx_a, code_a) in enumerate(codes):
        if not code_a:
            continue
        for idx_b, code_b in codes[i + 1:]:
            if not code_b:
                continue
            key = tuple(sorted((code_a, code_b)))
            if key in mutex_pairs:
                hits.append(
                    RuleHit(
                        rule_id="NCCI_MUTUALLY_EXCLUSIVE",
                        description=f"Mutually exclusive procedures {code_a} and {code_b} billed together",
                        weight=0.17,
                        severity="critical",
                        flag="ncci_mutex",
                        citation="CMS NCCI Mutually Exclusive Edits",
                        metadata={
                            "category": "ncci",
                            "line_indexes": [idx_a, idx_b],
                        },
                    )
                )
    return hits
