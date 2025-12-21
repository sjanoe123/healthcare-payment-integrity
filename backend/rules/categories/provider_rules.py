"""Provider-related rules (specialty, geographic, billing patterns)."""

from __future__ import annotations

from typing import Any

from backend.rules.models import RuleContext, RuleHit


def provider_outlier_rule(context: RuleContext) -> list[RuleHit]:
    """Check for provider-related outliers (specialty, geographic, billing patterns)."""
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
        distance = context.claim.get("service_distance_km") or provider.get(
            "distance_km"
        )
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
