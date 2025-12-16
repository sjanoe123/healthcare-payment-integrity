"""Threshold configuration for decision modes."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdConfig:
    recommendation_min: float = 0.6
    soft_hold_min: float = 0.8
    auto_approve_min: float = 0.9
    fast_path_min: float = 0.95
    guardrail_min: float = 0.7

    def decision_mode(self, score: float) -> str:
        if score >= self.auto_approve_min:
            return "auto_approve_fast" if score >= self.fast_path_min else "auto_approve"
        if score >= self.soft_hold_min:
            return "soft_hold"
        if score >= self.recommendation_min:
            return "recommendation"
        return "informational"

    @staticmethod
    def clamp_score(score: float) -> float:
        if score < 0.0:
            return 0.0
        if score > 1.0:
            return 1.0
        return score
