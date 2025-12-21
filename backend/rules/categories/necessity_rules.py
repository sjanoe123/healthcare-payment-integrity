"""Medical necessity rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit
from backend.utils import parse_flexible_date


def necessity_experimental_rule(context: RuleContext) -> list[RuleHit]:
    """Flag experimental or investigational procedures."""
    experimental_codes = context.datasets.get("experimental_codes", set())
    lcd = context.datasets.get("lcd", {})
    hits: list[RuleHit] = []

    for idx, item in enumerate(context.claim.get("items", [])):
        code = item.get("procedure_code")
        if not code:
            continue

        is_experimental = False
        source = None

        if code in experimental_codes:
            is_experimental = True
            source = "Experimental Code List"

        lcd_entry = lcd.get(code)
        if lcd_entry and lcd_entry.get("experimental"):
            is_experimental = True
            source = "CMS LCD/NCD"

        if is_experimental:
            hits.append(
                RuleHit(
                    rule_id="NECESSITY_EXPERIMENTAL",
                    description=f"Procedure {code} is experimental/investigational",
                    weight=0.18,
                    severity="high",
                    flag="necessity_experimental",
                    citation=source,
                    metadata={
                        "category": "necessity",
                        "line_index": idx,
                        "procedure_code": code,
                    },
                )
            )

    return hits


def necessity_frequency_rule(context: RuleContext) -> list[RuleHit]:
    """Check if services exceed frequency limits per policy."""
    frequency_limits = context.datasets.get("frequency_limits", {})
    service_history = context.datasets.get("service_history", {})
    claim = context.claim
    member_id = claim.get("member", {}).get("member_id")
    service_date_str = claim.get("service_date") or claim.get("dos")

    if not member_id or not frequency_limits:
        return []

    service_date = parse_flexible_date(service_date_str)
    if not service_date:
        return []

    member_history = service_history.get(member_id, {})
    hits: list[RuleHit] = []

    for idx, item in enumerate(claim.get("items", [])):
        code = item.get("procedure_code")
        if not code or code not in frequency_limits:
            continue

        limit = frequency_limits[code]
        max_per_year = limit.get("max_per_year")
        max_per_lifetime = limit.get("max_per_lifetime")
        min_days_between = limit.get("min_days_between")

        code_history = member_history.get(
            code, {"count_ytd": 0, "count_lifetime": 0, "last_date": None}
        )

        if max_per_year and code_history.get("count_ytd", 0) >= max_per_year:
            hits.append(
                RuleHit(
                    rule_id="NECESSITY_FREQUENCY_EXCEEDED",
                    description=f"Procedure {code}: annual limit of {max_per_year} already reached",
                    weight=0.15,
                    severity="high",
                    flag="necessity_frequency",
                    citation="Medical Policy Frequency Limits",
                    metadata={
                        "category": "necessity",
                        "line_index": idx,
                        "procedure_code": code,
                        "limit_type": "annual",
                        "limit": max_per_year,
                        "current_count": code_history.get("count_ytd", 0),
                    },
                )
            )

        if (
            max_per_lifetime
            and code_history.get("count_lifetime", 0) >= max_per_lifetime
        ):
            hits.append(
                RuleHit(
                    rule_id="NECESSITY_FREQUENCY_EXCEEDED",
                    description=f"Procedure {code}: lifetime limit of {max_per_lifetime} already reached",
                    weight=0.18,
                    severity="critical",
                    flag="necessity_frequency",
                    citation="Medical Policy Frequency Limits",
                    metadata={
                        "category": "necessity",
                        "line_index": idx,
                        "procedure_code": code,
                        "limit_type": "lifetime",
                        "limit": max_per_lifetime,
                        "current_count": code_history.get("count_lifetime", 0),
                    },
                )
            )

        if min_days_between and code_history.get("last_date"):
            last_date = parse_flexible_date(code_history["last_date"])
            if last_date:
                days_since = (service_date - last_date).days
                if days_since < min_days_between:
                    hits.append(
                        RuleHit(
                            rule_id="NECESSITY_FREQUENCY_TOO_SOON",
                            description=f"Procedure {code}: only {days_since} days since last service, minimum is {min_days_between}",
                            weight=0.14,
                            severity="high",
                            flag="necessity_frequency",
                            citation="Medical Policy Frequency Limits",
                            metadata={
                                "category": "necessity",
                                "line_index": idx,
                                "procedure_code": code,
                                "days_since_last": days_since,
                                "min_days_required": min_days_between,
                            },
                        )
                    )

    return hits
