"""Healthcare fraud detection rules."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any

from .models import RuleContext, RuleHit
from .registry import RuleRegistry

Rule = Callable[[RuleContext], list[RuleHit]]


def register_default_rules(registry: RuleRegistry) -> None:
    registry.extend(
        [
            high_dollar_rule,
            reimbursement_outlier_rule,
            ncci_ptp_rule,
            ncci_mue_rule,
            lcd_coverage_rule,
            lcd_age_gender_rule,
            lcd_experimental_rule,
            global_surgery_modifier_rule,
            oig_exclusion_rule,
            fwa_watchlist_rule,
            provider_outlier_rule,
            duplicate_line_rule,
            misc_code_rule,
        ]
    )


def high_dollar_rule(context: RuleContext) -> list[RuleHit]:
    tiers = context.config.get("high_dollar_tiers", [(10000, 0.1), (25000, 0.15)])
    total_billed = sum(item.get("line_amount", 0) for item in context.claim.get("items", []))
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


def ncci_ptp_rule(context: RuleContext) -> list[RuleHit]:
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


def lcd_coverage_rule(context: RuleContext) -> list[RuleHit]:
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
                in_range = any((r.get("min", 0) <= age <= r.get("max", age)) for r in ranges if r)
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
    mpfs: dict[str, dict[str, Any]] = context.datasets.get("mpfs", {})
    items = context.claim.get("items", [])
    has_eval = any((str(item.get("procedure_code", "")).startswith("99")) for item in items)
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


def oig_exclusion_rule(context: RuleContext) -> list[RuleHit]:
    exclusions = context.datasets.get("oig_exclusions", set())
    provider = context.claim.get("provider", {})
    npi = provider.get("npi") or provider.get("billing_npi")
    if npi and npi in exclusions:
        return [
            RuleHit(
                rule_id="OIG_EXCLUSION",
                description=f"Provider NPI {npi} is on OIG exclusion list",
                weight=0.25,
                severity="critical",
                flag="oig_excluded_provider",
                citation="OIG LEIE",
                metadata={"category": "provider", "npi": npi},
            )
        ]
    return []


def fwa_watchlist_rule(context: RuleContext) -> list[RuleHit]:
    watchlist = context.datasets.get("fwa_watchlist", set())
    provider = context.claim.get("provider", {})
    npi = provider.get("npi") or provider.get("billing_npi")
    if npi and npi in watchlist:
        return [
            RuleHit(
                rule_id="FWA_WATCH",
                description=f"Provider NPI {npi} appears on fraud watchlist",
                weight=0.12,
                severity="high",
                flag="fwa_watch_provider",
                citation="Internal FWA Watchlist",
                metadata={"category": "provider", "npi": npi},
            )
        ]
    return []


def provider_outlier_rule(context: RuleContext) -> list[RuleHit]:
    utilization: dict[str, dict[str, Any]] = context.datasets.get("utilization", {})
    fwa_config: dict[str, Any] = context.datasets.get("fwa_config", {})
    roi_multiplier = fwa_config.get("roi_multiplier", 1.0)
    volume_threshold = fwa_config.get("volume_threshold", 3)
    high_risk_specialties = {
        str(value).lower() for value in fwa_config.get("high_risk_specialties", [])
    }
    distance_limit = fwa_config.get("geographic_distance_km")
    hits: list[RuleHit] = []
    provider = context.claim.get("provider", {})
    specialty = str(provider.get("specialty", "")).lower()
    if specialty and specialty in high_risk_specialties:
        hits.append(
            RuleHit(
                rule_id="FWA_HIGH_RISK_SPECIALTY",
                description=f"Provider specialty {specialty} flagged high risk",
                weight=0.08,
                severity="medium",
                flag="high_risk_specialty",
                citation="FWA configuration",
                metadata={"category": "provider", "specialty": specialty},
            )
        )

    if distance_limit:
        distance = context.claim.get("service_distance_km") or provider.get("distance_km")
        if distance is None:
            for item in context.claim.get("items", []):
                if item.get("service_distance_km") is not None:
                    distance = item["service_distance_km"]
                    break
        if isinstance(distance, (int, float)) and distance > distance_limit:
            hits.append(
                RuleHit(
                    rule_id="GEOGRAPHIC_DISTANCE_OUTLIER",
                    description=f"Service distance {distance:.1f}km exceeds configured limit {distance_limit}km",
                    weight=0.1,
                    severity="medium",
                    flag="geographic_outlier",
                    citation="FWA configuration",
                    metadata={
                        "category": "provider",
                        "distance_km": distance,
                        "limit_km": distance_limit,
                    },
                )
            )

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        quantity = item.get("quantity") or 0
        amount = item.get("line_amount") or 0
        metrics = utilization.get(code)
        if metrics is None:
            continue
        pctile_99 = metrics.get("pctile_99") or 0
        roi_estimate = 0.0
        if pctile_99 and amount > pctile_99:
            roi_estimate = (amount - pctile_99) * roi_multiplier
            hits.append(
                RuleHit(
                    rule_id="UTIL_AMOUNT_OUTLIER",
                    description=f"{code} amount ${amount:,.2f} exceeds 99th percentile ${pctile_99:,.2f}",
                    weight=0.15,
                    severity="high",
                    flag="amount_outlier",
                    citation="CMS Utilization",
                    metadata={
                        "category": "financial",
                        "line_index": idx,
                        "pctile_99": pctile_99,
                        "estimated_roi": roi_estimate,
                    },
                )
            )
        if quantity >= metrics.get("avg_units", 0) * volume_threshold:
            hits.append(
                RuleHit(
                    rule_id="UTIL_VOLUME_OUTLIER",
                    description=f"{code} quantity {quantity} exceeds volume threshold",
                    weight=0.1,
                    severity="medium",
                    flag="volume_outlier",
                    citation="CMS Utilization",
                    metadata={
                        "category": "financial",
                        "line_index": idx,
                        "avg_units": metrics.get("avg_units", 0),
                        "volume_threshold": volume_threshold,
                    },
                )
            )
    return hits


def duplicate_line_rule(context: RuleContext) -> list[RuleHit]:
    items = context.claim.get("items", [])
    counter = Counter((item.get("procedure_code"), item.get("modifier")) for item in items)
    hits: list[RuleHit] = []
    for (code, modifier), count in counter.items():
        if code and count > 1:
            hits.append(
                RuleHit(
                    rule_id="DUPLICATE_LINE",
                    description=f"Procedure {code} repeated {count} times",
                    weight=0.08,
                    severity="medium",
                    flag="duplicate_line",
                    metadata={"category": "financial", "modifier": modifier, "count": count},
                )
            )
    return hits


def misc_code_rule(context: RuleContext) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code", "")
        if code.startswith("99"):
            hits.append(
                RuleHit(
                    rule_id="MISC_CODE",
                    description=f"Procedure {code} is miscellaneous (99-prefix)",
                    weight=0.05,
                    severity="low",
                    flag="misc_code",
                    metadata={"category": "financial", "line_index": idx},
                )
            )
    return hits
