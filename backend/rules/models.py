"""Data models for the rules engine."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuleHit:
    """Represents a single rule evaluation impact."""

    rule_id: str
    description: str
    weight: float
    severity: str
    flag: str
    citation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleResult:
    """Container for all rule hits and aggregate score adjustments."""

    hits: list[RuleHit] = field(default_factory=list)
    score_delta: float = 0.0
    roi_estimate: float | None = None

    def add_hit(self, hit: RuleHit) -> None:
        self.hits.append(hit)
        self.score_delta += hit.weight
        estimated_roi = hit.metadata.get("estimated_roi")
        if estimated_roi is not None:
            current = self.roi_estimate or 0.0
            with suppress(TypeError, ValueError):
                self.roi_estimate = current + float(estimated_roi)


@dataclass(frozen=True)
class DecisionOutcome:
    score: float
    confidence: float
    decision_mode: str


@dataclass(frozen=True)
class BaselineOutcome:
    decision: DecisionOutcome
    rule_result: RuleResult
    ncci_flags: list[str]
    coverage_flags: list[str]
    provider_flags: list[str]
    roi_estimate: float | None


@dataclass(frozen=True)
class RuleContext:
    """Inputs required to evaluate baseline rules."""

    claim: dict[str, Any]
    datasets: dict[str, Any]
    config: dict[str, Any]
