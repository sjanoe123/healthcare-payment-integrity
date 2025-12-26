"""Surgical package and procedure rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit
from backend.utils import parse_flexible_date


def surgical_global_period_rule(context: RuleContext) -> list[RuleHit]:
    """Check for separate billing during global surgical period."""
    global_surgery_data = context.datasets.get("global_surgery", {})
    surgical_history = context.datasets.get("surgical_history", {})
    claim = context.claim
    member_id = claim.get("member", {}).get("member_id")
    service_date_str = claim.get("service_date") or claim.get("dos")

    if not member_id or not service_date_str:
        return []

    service_date = parse_flexible_date(service_date_str)
    if not service_date:
        return []

    member_surgeries = surgical_history.get(member_id, [])
    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code")
        if not code:
            continue

        modifiers = set(item.get("modifiers", []))
        if item.get("modifier"):
            modifiers.add(item.get("modifier"))

        if modifiers.intersection({"24", "25", "57", "58", "78", "79"}):
            continue

        for surgery in member_surgeries:
            surgery_code = surgery.get("procedure_code")
            surgery_date = parse_flexible_date(surgery.get("service_date", ""))
            if not surgery_date:
                continue

            global_days = global_surgery_data.get(surgery_code, {}).get(
                "global_days", 0
            )
            if not global_days:
                continue

            days_post = (service_date - surgery_date).days
            if 0 < days_post <= global_days:
                hits.append(
                    RuleHit(
                        rule_id="SURGICAL_GLOBAL_PERIOD",
                        rule_type="coverage",
                        description=f"Procedure {code} billed {days_post} days post {surgery_code} (global: {global_days} days)",
                        weight=0.15,
                        severity="high",
                        flag="surgical_global_period",
                        citation="CMS Global Surgery Policy",
                        metadata={
                            "category": "surgical",
                            "line_index": idx,
                            "billed_code": code,
                            "surgery_code": surgery_code,
                            "days_post_surgery": days_post,
                            "global_period_days": global_days,
                        },
                    )
                )
                break

    return hits


def surgical_multiple_procedure_rule(context: RuleContext) -> list[RuleHit]:
    """Check for multiple procedures without proper discount modifier."""
    multiple_procedure_codes = context.datasets.get("multiple_procedure_codes", set())
    hits: list[RuleHit] = []

    items = context.claim.get("items", [])
    surgical_codes = []

    for idx, item in enumerate(items):
        code = item.get("procedure_code")
        if not code:
            continue

        if code in multiple_procedure_codes or (
            code.isdigit() and 10000 <= int(code) <= 69999
        ):
            modifiers = set(item.get("modifiers", []))
            if item.get("modifier"):
                modifiers.add(item.get("modifier"))
            surgical_codes.append((idx, code, modifiers))

    if len(surgical_codes) <= 1:
        return []

    has_primary = False
    secondary_without_51 = []

    for idx, code, modifiers in surgical_codes:
        if "51" in modifiers:
            continue
        if not has_primary:
            has_primary = True
        else:
            secondary_without_51.append((idx, code))

    for idx, code in secondary_without_51:
        hits.append(
            RuleHit(
                rule_id="SURGICAL_MULTIPLE_NO_51",
                rule_type="coverage",
                description=f"Multiple procedure {code} billed without modifier 51",
                weight=0.11,
                severity="medium",
                flag="surgical_multiple_procedure",
                citation="CMS Multiple Procedure Policy",
                metadata={
                    "category": "surgical",
                    "line_index": idx,
                    "procedure_code": code,
                },
            )
        )

    return hits


def surgical_assistant_rule(context: RuleContext) -> list[RuleHit]:
    """Check for assistant surgeon billing compliance."""
    assistant_allowed = context.datasets.get("assistant_allowed_codes", set())
    hits: list[RuleHit] = []

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        if not code:
            continue

        modifiers = set(item.get("modifiers", []))
        if item.get("modifier"):
            modifiers.add(item.get("modifier"))

        assistant_modifiers = {"80", "81", "82", "AS"}
        has_assistant = bool(modifiers.intersection(assistant_modifiers))

        if not has_assistant:
            continue

        if assistant_allowed and code not in assistant_allowed:
            hits.append(
                RuleHit(
                    rule_id="SURGICAL_ASSISTANT_NOT_ALLOWED",
                    rule_type="coverage",
                    description=f"Assistant surgeon modifier used on {code} which doesn't allow assistants",
                    weight=0.13,
                    severity="high",
                    flag="surgical_assistant",
                    citation="CMS Assistant Surgeon Policy",
                    metadata={
                        "category": "surgical",
                        "line_index": idx,
                        "procedure_code": code,
                        "modifiers": list(modifiers),
                    },
                )
            )

    return hits


def surgical_cosurgeon_rule(context: RuleContext) -> list[RuleHit]:
    """Check for co-surgeon billing compliance."""
    cosurgeon_allowed = context.datasets.get("cosurgeon_allowed_codes", set())
    hits: list[RuleHit] = []

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        if not code:
            continue

        modifiers = set(item.get("modifiers", []))
        if item.get("modifier"):
            modifiers.add(item.get("modifier"))

        if "62" not in modifiers:
            continue

        if cosurgeon_allowed and code not in cosurgeon_allowed:
            hits.append(
                RuleHit(
                    rule_id="SURGICAL_COSURGEON_NOT_ALLOWED",
                    rule_type="coverage",
                    description=f"Co-surgeon modifier 62 used on {code} which doesn't allow co-surgeons",
                    weight=0.13,
                    severity="high",
                    flag="surgical_cosurgeon",
                    citation="CMS Co-Surgeon Policy",
                    metadata={
                        "category": "surgical",
                        "line_index": idx,
                        "procedure_code": code,
                    },
                )
            )

    return hits


def surgical_bilateral_rule(context: RuleContext) -> list[RuleHit]:
    """Check for bilateral procedure billing compliance."""
    bilateral_allowed = context.datasets.get("bilateral_allowed_codes", set())
    bilateral_indicators = context.datasets.get("bilateral_indicators", {})
    hits: list[RuleHit] = []

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        if not code:
            continue

        modifiers = set(item.get("modifiers", []))
        if item.get("modifier"):
            modifiers.add(item.get("modifier"))

        if "50" not in modifiers:
            continue

        indicator = bilateral_indicators.get(code, "1")

        if indicator == "0":
            hits.append(
                RuleHit(
                    rule_id="SURGICAL_BILATERAL_150",
                    rule_type="coverage",
                    description=f"Bilateral modifier 50 on {code} but payment already includes bilateral",
                    weight=0.12,
                    severity="medium",
                    flag="surgical_bilateral",
                    citation="CMS Bilateral Procedure Policy",
                    metadata={
                        "category": "surgical",
                        "line_index": idx,
                        "procedure_code": code,
                        "bilateral_indicator": indicator,
                    },
                )
            )

        if indicator == "9":
            hits.append(
                RuleHit(
                    rule_id="SURGICAL_BILATERAL_NOT_APPLICABLE",
                    rule_type="coverage",
                    description=f"Bilateral modifier 50 not applicable to {code}",
                    weight=0.14,
                    severity="high",
                    flag="surgical_bilateral",
                    citation="CMS Bilateral Procedure Policy",
                    metadata={
                        "category": "surgical",
                        "line_index": idx,
                        "procedure_code": code,
                        "bilateral_indicator": indicator,
                    },
                )
            )

        if (
            bilateral_allowed
            and code not in bilateral_allowed
            and indicator not in {"0", "1", "2", "3"}
        ):
            hits.append(
                RuleHit(
                    rule_id="SURGICAL_BILATERAL_NOT_ALLOWED",
                    rule_type="coverage",
                    description=f"Bilateral modifier 50 used on {code} which doesn't allow bilateral billing",
                    weight=0.14,
                    severity="high",
                    flag="surgical_bilateral",
                    citation="CMS Bilateral Procedure Policy",
                    metadata={
                        "category": "surgical",
                        "line_index": idx,
                        "procedure_code": code,
                    },
                )
            )

    return hits
