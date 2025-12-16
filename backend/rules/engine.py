"""Core rules evaluation engine."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from . import ruleset
from .models import BaselineOutcome, DecisionOutcome, RuleContext, RuleResult
from .registry import default_registry
from .thresholds import ThresholdConfig


def evaluate_baseline(
    claim: dict[str, Any],
    datasets: dict[str, Any],
    config: dict[str, Any] | None = None,
    threshold_config: ThresholdConfig | None = None,
) -> BaselineOutcome:
    """Evaluate claim against baseline rules and return aggregated outcome."""

    config = config or {}
    threshold_config = threshold_config or ThresholdConfig()

    context = RuleContext(claim=claim, datasets=datasets, config=config)
    rule_result = RuleResult()
    ncci_flags: list[str] = []
    coverage_flags: list[str] = []
    provider_flags: list[str] = []

    # ensure default registry is populated
    ruleset.register_default_rules(default_registry)

    rule_overrides: dict[str, dict[str, Any]] = config.get("rule_overrides", {})

    for rule in default_registry.active_rules():
        hits = rule(context)
        if not hits:
            continue
        for hit in hits:
            override = rule_overrides.get(hit.rule_id)
            adjusted_hit = hit
            if override:
                if not override.get("enabled", True):
                    continue
                adjusted_hit = replace(
                    hit,
                    weight=float(override.get("weight", hit.weight)),
                    severity=str(override.get("severity", hit.severity)),
                )
            rule_result.add_hit(adjusted_hit)
            if adjusted_hit.metadata.get("category") == "ncci":
                ncci_flags.append(adjusted_hit.flag)
            if adjusted_hit.metadata.get("category") == "coverage":
                coverage_flags.append(adjusted_hit.flag)
            if adjusted_hit.metadata.get("category") == "provider":
                provider_flags.append(adjusted_hit.flag)

    base_score = config.get("base_score", 0.5)
    score = base_score + rule_result.score_delta
    score = ThresholdConfig.clamp_score(score)
    confidence = score  # For MVP, confidence aligns with score
    decision_mode = threshold_config.decision_mode(score)

    outcome = BaselineOutcome(
        decision=DecisionOutcome(score=score, confidence=confidence, decision_mode=decision_mode),
        rule_result=rule_result,
        ncci_flags=list(dict.fromkeys(ncci_flags)),
        coverage_flags=list(dict.fromkeys(coverage_flags)),
        provider_flags=list(dict.fromkeys(provider_flags)),
        roi_estimate=rule_result.roi_estimate,
    )

    return outcome
