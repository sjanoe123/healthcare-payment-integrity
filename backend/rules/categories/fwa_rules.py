"""Fraud, Waste, and Abuse (FWA) detection rules."""

from __future__ import annotations

from backend.rules.models import RuleContext, RuleHit


def oig_exclusion_rule(context: RuleContext) -> list[RuleHit]:
    """Check if provider NPI is on OIG exclusion list."""
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
    """Check if provider NPI is on internal fraud watchlist."""
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


def fwa_volume_spike_rule(context: RuleContext) -> list[RuleHit]:
    """Detect sudden spikes in provider billing volume."""
    provider_history = context.datasets.get("provider_history", {})
    provider = context.claim.get("provider", {})
    npi = provider.get("npi") or provider.get("billing_npi")
    if not npi or npi not in provider_history:
        return []

    history = provider_history[npi]
    avg_monthly_claims = history.get("avg_monthly_claims", 0)
    current_month_claims = history.get("current_month_claims", 0)
    spike_threshold = context.config.get("volume_spike_threshold", 2.0)

    if (
        avg_monthly_claims > 0
        and current_month_claims > avg_monthly_claims * spike_threshold
    ):
        return [
            RuleHit(
                rule_id="FWA_VOLUME_SPIKE",
                description=f"Provider billing volume spike: {current_month_claims} claims vs {avg_monthly_claims:.0f} average",
                weight=0.14,
                severity="high",
                flag="fwa_volume_spike",
                citation="Internal FWA Analytics",
                metadata={
                    "category": "provider",
                    "npi": npi,
                    "current_claims": current_month_claims,
                    "average_claims": avg_monthly_claims,
                    "spike_ratio": current_month_claims / avg_monthly_claims,
                },
            )
        ]
    return []


def fwa_pattern_rule(context: RuleContext) -> list[RuleHit]:
    """Detect suspicious billing patterns (same diagnosis on unrelated services)."""
    hits: list[RuleHit] = []
    items = context.claim.get("items", [])
    diagnosis_codes = context.claim.get("diagnosis_codes", [])

    if len(items) < 3 or len(diagnosis_codes) < 1:
        return []

    primary_dx = diagnosis_codes[0] if diagnosis_codes else None
    if not primary_dx:
        return []

    procedure_categories = context.datasets.get("procedure_categories", {})
    categories_used = set()

    for item in items:
        code = item.get("procedure_code")
        if code and code in procedure_categories:
            categories_used.add(procedure_categories[code].get("category"))

    if len(categories_used) >= 3:
        hits.append(
            RuleHit(
                rule_id="FWA_PATTERN_SUSPICIOUS",
                description=f"Same primary diagnosis {primary_dx} used across {len(categories_used)} unrelated service categories",
                weight=0.10,
                severity="medium",
                flag="fwa_pattern",
                citation="Internal FWA Analytics",
                metadata={
                    "category": "provider",
                    "primary_diagnosis": primary_dx,
                    "service_categories": list(categories_used),
                },
            )
        )
    return hits
