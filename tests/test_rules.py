"""Tests for the rules engine."""

from __future__ import annotations

from rules import evaluate_baseline, ThresholdConfig


class TestRulesEngine:
    """Test the fraud detection rules engine."""

    def test_evaluate_baseline_returns_outcome(
        self, sample_claim: dict, sample_datasets: dict
    ):
        """Test that evaluate_baseline returns a valid outcome."""
        outcome = evaluate_baseline(
            claim=sample_claim,
            datasets=sample_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        assert outcome is not None
        assert hasattr(outcome, "decision")
        assert hasattr(outcome, "rule_result")
        assert 0.0 <= outcome.decision.score <= 1.0

    def test_detects_oig_exclusion(self, sample_claim: dict, sample_datasets: dict):
        """Test that OIG excluded providers are flagged."""
        outcome = evaluate_baseline(
            claim=sample_claim,
            datasets=sample_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        # Provider NPI 1234567890 is in the exclusion list
        # Check rule hits for OIG exclusion
        oig_hits = [h for h in outcome.rule_result.hits if h.rule_id == "OIG_EXCLUSION"]
        assert len(oig_hits) > 0, "Expected OIG exclusion rule to be triggered"
        assert "oig_excluded_provider" in outcome.provider_flags

    def test_detects_ncci_ptp_edit(self, sample_claim: dict, sample_datasets: dict):
        """Test that NCCI PTP edits are detected."""
        outcome = evaluate_baseline(
            claim=sample_claim,
            datasets=sample_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        # Claim has 99214 and 99215 which is a PTP pair
        assert len(outcome.ncci_flags) > 0

    def test_detects_mue_violation(self, sample_claim: dict, sample_datasets: dict):
        """Test that MUE violations are detected."""
        outcome = evaluate_baseline(
            claim=sample_claim,
            datasets=sample_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        # Claim has 99213 with quantity 2, but MUE limit is 1
        rule_hits = outcome.rule_result.hits
        mue_hits = [h for h in rule_hits if "MUE" in h.rule_id]
        assert len(mue_hits) > 0

    def test_clean_claim_low_score(self, clean_claim: dict, sample_datasets: dict):
        """Test that clean claims get lower fraud scores."""
        # Remove the excluded NPI from datasets
        datasets = sample_datasets.copy()
        datasets["oig_exclusions"] = set()

        outcome = evaluate_baseline(
            claim=clean_claim,
            datasets=datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        # Clean claim should have fewer rule hits
        assert len(outcome.rule_result.hits) == 0 or outcome.decision.score < 0.7

    def test_high_risk_claim_elevated_score(
        self, sample_claim: dict, sample_datasets: dict
    ):
        """Test that high-risk claims get elevated fraud scores."""
        outcome = evaluate_baseline(
            claim=sample_claim,
            datasets=sample_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        # Claim has multiple fraud indicators, should be flagged
        assert outcome.decision.score > 0.5
        assert len(outcome.rule_result.hits) > 0


class TestThresholdConfig:
    """Test threshold configuration."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        config = ThresholdConfig()

        assert config.recommendation_min == 0.6
        assert config.soft_hold_min == 0.8
        assert config.auto_approve_min == 0.9

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        config = ThresholdConfig(recommendation_min=0.5, soft_hold_min=0.7)

        assert config.recommendation_min == 0.5
        assert config.soft_hold_min == 0.7

    def test_decision_mode_informational(self):
        """Test informational decision mode for low scores."""
        config = ThresholdConfig()
        assert config.decision_mode(0.3) == "informational"

    def test_decision_mode_recommendation(self):
        """Test recommendation decision mode."""
        config = ThresholdConfig()
        assert config.decision_mode(0.65) == "recommendation"

    def test_decision_mode_soft_hold(self):
        """Test soft hold decision mode."""
        config = ThresholdConfig()
        assert config.decision_mode(0.85) == "soft_hold"

    def test_clamp_score(self):
        """Test score clamping."""
        assert ThresholdConfig.clamp_score(-0.5) == 0.0
        assert ThresholdConfig.clamp_score(1.5) == 1.0
        assert ThresholdConfig.clamp_score(0.5) == 0.5
