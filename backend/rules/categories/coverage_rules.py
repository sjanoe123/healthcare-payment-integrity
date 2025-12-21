"""Coverage and LCD/NCD compliance rules."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from backend.rules.models import RuleContext, RuleHit


def lcd_coverage_rule(context: RuleContext) -> list[RuleHit]:
    """Check if procedures have covered diagnoses per LCD/NCD."""
    dataset = context.datasets.get("lcd", {})
    hits: list[RuleHit] = []
    diagnosis_codes = set(context.claim.get("diagnosis_codes", []))
    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        allowed = dataset.get(code)
        if allowed is None:
            continue
        allowed_diagnoses = allowed.get("diagnosis_codes", set())
        if not diagnosis_codes.intersection(allowed_diagnoses):
            hits.append(
                RuleHit(
                    rule_id="LCD_MISMATCH",
                    description=f"{code} lacks covered diagnosis per LCD/NCD",
                    weight=-0.2,
                    severity="high",
                    flag="lcd_non_covered",
                    citation="CMS LCD/NCD",
                    metadata={
                        "category": "coverage",
                        "line_index": idx,
                        "allowed_diagnoses": sorted(allowed_diagnoses),
                    },
                )
            )
    return hits


def lcd_age_gender_rule(context: RuleContext) -> list[RuleHit]:
    """Check for age or gender conflicts with LCD guidance."""
    dataset = context.datasets.get("lcd", {})
    member = context.claim.get("member", {}) or context.claim.get("patient", {})
    age = member.get("age")
    gender = (member.get("gender") or "").upper()
    if age is None and not gender:
        return []
    hits: list[RuleHit] = []
    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        lcd_entry = dataset.get(code)
        if not lcd_entry:
            continue
        if age is not None:
            ranges = lcd_entry.get("age_ranges", [])
            if ranges:
                in_range = any(
                    (r.get("min", 0) <= age <= r.get("max", age)) for r in ranges if r
                )
                if not in_range:
                    hits.append(
                        RuleHit(
                            rule_id="LCD_AGE_CONFLICT",
                            description=f"{code} age {age} outside LCD guidance",
                            weight=-0.15,
                            severity="high",
                            flag="lcd_age_mismatch",
                            citation="CMS LCD/NCD",
                            metadata={
                                "category": "coverage",
                                "line_index": idx,
                                "age": age,
                                "allowed_age_ranges": ranges,
                            },
                        )
                    )
        genders = lcd_entry.get("genders") or set()
        if genders and gender and gender not in genders:
            hits.append(
                RuleHit(
                    rule_id="LCD_GENDER_CONFLICT",
                    description=f"{code} gender {gender} outside LCD guidance",
                    weight=-0.1,
                    severity="medium",
                    flag="lcd_gender_mismatch",
                    citation="CMS LCD/NCD",
                    metadata={
                        "category": "coverage",
                        "line_index": idx,
                        "allowed_genders": sorted(genders),
                    },
                )
            )
    return hits


def lcd_experimental_rule(context: RuleContext) -> list[RuleHit]:
    """Flag experimental or investigational procedures."""
    dataset = context.datasets.get("lcd", {})
    hits: list[RuleHit] = []
    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        lcd_entry = dataset.get(code)
        if lcd_entry and lcd_entry.get("experimental"):
            hits.append(
                RuleHit(
                    rule_id="LCD_EXPERIMENTAL",
                    description=f"{code} marked experimental/investigational",
                    weight=0.14,
                    severity="high",
                    flag="experimental_code",
                    citation="CMS LCD/NCD",
                    metadata={"category": "coverage", "line_index": idx},
                )
            )
    return hits


def global_surgery_modifier_rule(context: RuleContext) -> list[RuleHit]:
    """Check for missing modifiers on global surgery codes with E/M services."""
    mpfs: dict[str, dict[str, Any]] = context.datasets.get("mpfs", {})
    items = context.claim.get("items", [])
    has_eval = any(
        (str(item.get("procedure_code", "")).startswith("99")) for item in items
    )
    hits: list[RuleHit] = []
    if not has_eval:
        return hits
    for idx, item in enumerate(items):
        code = item.get("procedure_code")
        if not code or code not in mpfs:
            continue
        indicator = mpfs[code].get("global_surgery")
        if indicator in {"090", "010"}:
            modifiers: Sequence[str] = item.get("modifiers") or []
            single_modifier = item.get("modifier")
            if single_modifier and single_modifier not in modifiers:
                modifiers = [*list(modifiers), single_modifier]
            modifiers = [m for m in modifiers if m]
            if modifiers and any(m in {"25", "57"} for m in modifiers):
                continue
            hits.append(
                RuleHit(
                    rule_id="GLOBAL_SURGERY_NO_MODIFIER",
                    description=f"{code} with global period lacks required modifier alongside E/M services",
                    weight=0.12,
                    severity="medium",
                    flag="global_surgery_no_modifier",
                    citation="CMS MPFS",
                    metadata={
                        "category": "coverage",
                        "line_index": idx,
                        "global_indicator": indicator,
                    },
                )
            )
    return hits
