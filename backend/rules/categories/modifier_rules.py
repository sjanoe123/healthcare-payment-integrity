"""Modifier validation rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit


def modifier_invalid_rule(context: RuleContext) -> list[RuleHit]:
    """Check for invalid modifier use on procedures."""
    modifier_rules = context.datasets.get("modifier_rules", {})
    valid_modifiers = context.datasets.get("valid_modifiers", set())
    hits: list[RuleHit] = []

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        modifiers = item.get("modifiers", [])
        single_modifier = item.get("modifier")
        if single_modifier and single_modifier not in modifiers:
            modifiers = list(modifiers) + [single_modifier]

        for modifier in modifiers:
            if not modifier:
                continue

            if valid_modifiers and modifier not in valid_modifiers:
                hits.append(
                    RuleHit(
                        rule_id="MODIFIER_INVALID",
                        rule_type="modifier",
                        description=f"Invalid modifier {modifier} on line {idx + 1}",
                        weight=0.12,
                        severity="medium",
                        flag="modifier_invalid",
                        citation="CMS Modifier Guidelines",
                        metadata={
                            "category": "modifier",
                            "line_index": idx,
                            "modifier": modifier,
                        },
                    )
                )
                continue

            code_rules = modifier_rules.get(code, {})
            disallowed = code_rules.get("disallowed_modifiers", [])
            if modifier in disallowed:
                hits.append(
                    RuleHit(
                        rule_id="MODIFIER_INVALID",
                        rule_type="modifier",
                        description=f"Modifier {modifier} not allowed with procedure {code}",
                        weight=0.14,
                        severity="high",
                        flag="modifier_invalid",
                        citation="CMS Modifier Guidelines",
                        metadata={
                            "category": "modifier",
                            "line_index": idx,
                            "procedure_code": code,
                            "modifier": modifier,
                        },
                    )
                )

    return hits


def modifier_missing_rule(context: RuleContext) -> list[RuleHit]:
    """Check for required modifiers that are missing."""
    modifier_rules = context.datasets.get("modifier_rules", {})
    hits: list[RuleHit] = []

    items = context.claim.get("items", [])
    all_modifiers_used = set()
    for item in items:
        mods = item.get("modifiers", [])
        if item.get("modifier"):
            mods = list(mods) + [item.get("modifier")]
        all_modifiers_used.update(mods)

    for idx, item in enumerate(items):
        code = item.get("procedure_code")
        if not code:
            continue

        code_rules = modifier_rules.get(code, {})
        required = code_rules.get("required_modifiers", [])

        item_modifiers = set(item.get("modifiers", []))
        if item.get("modifier"):
            item_modifiers.add(item.get("modifier"))

        for req_mod in required:
            if isinstance(req_mod, list):
                if not item_modifiers.intersection(set(req_mod)):
                    hits.append(
                        RuleHit(
                            rule_id="MODIFIER_MISSING",
                            rule_type="modifier",
                            description=f"Procedure {code} requires one of modifiers: {', '.join(req_mod)}",
                            weight=0.13,
                            severity="high",
                            flag="modifier_missing",
                            citation="CMS Modifier Guidelines",
                            metadata={
                                "category": "modifier",
                                "line_index": idx,
                                "required_modifiers": req_mod,
                            },
                        )
                    )
            else:
                if req_mod not in item_modifiers:
                    hits.append(
                        RuleHit(
                            rule_id="MODIFIER_MISSING",
                            rule_type="modifier",
                            description=f"Procedure {code} requires modifier {req_mod}",
                            weight=0.13,
                            severity="high",
                            flag="modifier_missing",
                            citation="CMS Modifier Guidelines",
                            metadata={
                                "category": "modifier",
                                "line_index": idx,
                                "required_modifier": req_mod,
                            },
                        )
                    )

    return hits


def modifier_59_abuse_rule(context: RuleContext) -> list[RuleHit]:
    """Check for inappropriate use of modifier 59 or X modifiers."""
    ncci_ptp = context.datasets.get("ncci_ptp", {})
    hits: list[RuleHit] = []

    items = context.claim.get("items", [])
    codes_with_59 = []

    for idx, item in enumerate(items):
        modifiers = set(item.get("modifiers", []))
        if item.get("modifier"):
            modifiers.add(item.get("modifier"))

        modifier_59_variants = {"59", "XE", "XS", "XP", "XU"}
        if modifiers.intersection(modifier_59_variants):
            codes_with_59.append((idx, item.get("procedure_code"), modifiers))

    for idx, code, modifiers in codes_with_59:
        has_ncci_conflict = False
        for other_idx, other_item in enumerate(items):
            if other_idx == idx:
                continue
            other_code = other_item.get("procedure_code")
            if not other_code:
                continue
            key = tuple(sorted((code, other_code)))
            if key in ncci_ptp:
                ptp_info = ncci_ptp[key]
                if ptp_info.get("modifier") == "1":
                    has_ncci_conflict = True
                    break

        if not has_ncci_conflict:
            hits.append(
                RuleHit(
                    rule_id="MODIFIER_59_ABUSE",
                    rule_type="modifier",
                    description=f"Modifier 59/X used on {code} without apparent NCCI edit conflict",
                    weight=0.11,
                    severity="medium",
                    flag="modifier_59_abuse",
                    citation="CMS NCCI Modifier Policy",
                    metadata={
                        "category": "modifier",
                        "line_index": idx,
                        "procedure_code": code,
                        "modifiers_used": list(modifiers),
                    },
                )
            )

    return hits


def modifier_bilateral_rule(context: RuleContext) -> list[RuleHit]:
    """Check for bilateral modifier issues."""
    bilateral_codes = context.datasets.get("bilateral_codes", set())
    hits: list[RuleHit] = []

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        if not code:
            continue

        modifiers = set(item.get("modifiers", []))
        if item.get("modifier"):
            modifiers.add(item.get("modifier"))

        has_50 = "50" in modifiers
        has_lt_rt = bool(modifiers.intersection({"LT", "RT"}))

        if bilateral_codes:
            if has_50 and code not in bilateral_codes:
                hits.append(
                    RuleHit(
                        rule_id="MODIFIER_BILATERAL_INVALID",
                        rule_type="modifier",
                        description=f"Bilateral modifier 50 used on non-bilateral procedure {code}",
                        weight=0.14,
                        severity="high",
                        flag="modifier_bilateral",
                        citation="CMS Bilateral Procedure Policy",
                        metadata={
                            "category": "modifier",
                            "line_index": idx,
                            "procedure_code": code,
                        },
                    )
                )

        if has_50 and has_lt_rt:
            hits.append(
                RuleHit(
                    rule_id="MODIFIER_BILATERAL_CONFLICT",
                    rule_type="modifier",
                    description=f"Both bilateral (50) and laterality (LT/RT) modifiers on {code}",
                    weight=0.12,
                    severity="medium",
                    flag="modifier_bilateral",
                    citation="CMS Bilateral Procedure Policy",
                    metadata={
                        "category": "modifier",
                        "line_index": idx,
                        "procedure_code": code,
                        "modifiers": list(modifiers),
                    },
                )
            )

    return hits
