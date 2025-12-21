"""Unit tests for Kirk AI claims review agent.

These tests do NOT make actual API calls and are safe to run in CI/CD.
For live API tests, see scripts/test_kirk_live.py (run manually).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add backend to path for imports
backend_path = str(Path(__file__).parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from kirk_config import KIRK_CONFIG, KIRK_SYSTEM_PROMPT, KirkConfig  # noqa: E402
from claude_client import build_kirk_prompt, format_rule_hits, get_kirk_analysis  # noqa: E402
from rules import RuleHit  # noqa: E402


class TestKirkConfig:
    """Test Kirk configuration dataclass."""

    def test_default_config_values(self):
        """Verify default configuration values are set correctly."""
        config = KirkConfig()

        assert config.name == "Kirk"
        assert config.role == "Healthcare Payment Integrity Auditor"
        assert config.model == "claude-sonnet-4-5-20250929"
        assert config.max_tokens == 1000
        assert config.temperature == 0.3
        assert config.verbosity == "detailed"
        assert config.cite_regulations is True
        assert config.include_recommendations is True
        assert config.max_recommendations == 5

    def test_custom_config_override(self):
        """Test that configuration values can be customized."""
        config = KirkConfig(
            name="CustomKirk",
            model="claude-3-opus-20240229",
            max_tokens=2000,
            temperature=0.5,
            verbosity="comprehensive",
        )

        assert config.name == "CustomKirk"
        assert config.model == "claude-3-opus-20240229"
        assert config.max_tokens == 2000
        assert config.temperature == 0.5
        assert config.verbosity == "comprehensive"

    def test_focus_areas_default(self):
        """Verify default focus areas are set."""
        config = KirkConfig()

        assert len(config.focus_areas) == 5
        assert "NCCI compliance" in config.focus_areas
        assert "Medical necessity" in config.focus_areas
        assert "Provider eligibility" in config.focus_areas

    def test_global_kirk_config_exists(self):
        """Verify global KIRK_CONFIG is available."""
        assert KIRK_CONFIG is not None
        assert KIRK_CONFIG.name == "Kirk"


class TestKirkSystemPrompt:
    """Test Kirk's system prompt."""

    def test_system_prompt_contains_expertise(self):
        """Verify system prompt includes Kirk's expertise areas."""
        assert "NCCI Procedure-to-Procedure" in KIRK_SYSTEM_PROMPT
        assert "LCD/NCD" in KIRK_SYSTEM_PROMPT
        assert "OIG exclusion" in KIRK_SYSTEM_PROMPT
        assert "Anti-Kickback" in KIRK_SYSTEM_PROMPT
        assert "Stark Law" in KIRK_SYSTEM_PROMPT

    def test_system_prompt_contains_format(self):
        """Verify system prompt includes response format instructions."""
        # Check for JSON format fields (updated from plain text format)
        assert "risk_summary" in KIRK_SYSTEM_PROMPT
        assert "severity" in KIRK_SYSTEM_PROMPT
        assert "findings" in KIRK_SYSTEM_PROMPT
        assert "recommendations" in KIRK_SYSTEM_PROMPT
        assert "confidence" in KIRK_SYSTEM_PROMPT

    def test_system_prompt_contains_style(self):
        """Verify system prompt includes communication style."""
        assert "Formal and precise" in KIRK_SYSTEM_PROMPT
        assert "cite specific regulations" in KIRK_SYSTEM_PROMPT


class TestBuildKirkPrompt:
    """Test prompt construction for Kirk."""

    def test_prompt_includes_claim_data(self):
        """Verify claim data is included in prompt."""
        claim = {"claim_id": "TEST-001", "billed_amount": 500.00}
        prompt = build_kirk_prompt(
            claim=claim,
            rule_hits=[],
            fraud_score=0.5,
            decision_mode="recommendation",
        )

        assert "TEST-001" in prompt
        assert "500.0" in prompt  # Python formats as 500.0

    def test_prompt_includes_rule_hits(self):
        """Verify rule violations are formatted correctly."""
        rule_hits = [
            RuleHit(
                rule_id="NCCI_PTP",
                description="PTP edit between codes",
                weight=0.2,
                severity="high",
                flag="ncci",
                citation="NCCI Policy Manual Ch. 1",
            ),
        ]
        prompt = build_kirk_prompt(
            claim={"claim_id": "TEST-001"},
            rule_hits=rule_hits,
            fraud_score=0.7,
            decision_mode="soft_hold",
        )

        assert "NCCI_PTP" in prompt
        assert "PTP edit between codes" in prompt
        assert "NCCI Policy Manual Ch. 1" in prompt
        assert "0.70" in prompt

    def test_prompt_includes_rag_context(self):
        """Verify RAG context is included when available."""
        rag_context = "NCCI PTP Edits: Procedure-to-procedure edits define..."
        prompt = build_kirk_prompt(
            claim={"claim_id": "TEST-001"},
            rule_hits=[],
            fraud_score=0.5,
            decision_mode="informational",
            rag_context=rag_context,
        )

        assert "Relevant Policy Context" in prompt
        assert rag_context in prompt

    def test_prompt_without_rag_context(self):
        """Verify prompt works without RAG context."""
        prompt = build_kirk_prompt(
            claim={"claim_id": "TEST-001"},
            rule_hits=[],
            fraud_score=0.3,
            decision_mode="informational",
            rag_context=None,
        )

        assert "Relevant Policy Context" not in prompt


class TestFormatRuleHits:
    """Test rule hit formatting."""

    def test_format_empty_hits(self):
        """Test formatting with no rule hits."""
        result = format_rule_hits([])
        assert result == "No rule violations detected."

    def test_format_single_hit(self):
        """Test formatting a single rule hit."""
        hits = [
            RuleHit(
                rule_id="OIG_EXCLUSION",
                description="Provider on OIG exclusion list",
                weight=0.5,
                severity="critical",
                flag="provider",
                citation="42 CFR 1001",
            ),
        ]
        result = format_rule_hits(hits)

        assert "[CRITICAL]" in result
        assert "OIG_EXCLUSION" in result
        assert "Provider on OIG exclusion list" in result
        assert "42 CFR 1001" in result

    def test_format_multiple_hits(self):
        """Test formatting multiple rule hits."""
        hits = [
            RuleHit(
                rule_id="NCCI_PTP",
                description="PTP edit detected",
                weight=0.2,
                severity="high",
                flag="ncci",
            ),
            RuleHit(
                rule_id="NCCI_MUE",
                description="MUE violation",
                weight=0.15,
                severity="medium",
                flag="ncci",
            ),
        ]
        result = format_rule_hits(hits)

        assert "[HIGH]" in result
        assert "[MEDIUM]" in result
        assert "NCCI_PTP" in result
        assert "NCCI_MUE" in result


class TestGetKirkAnalysisFallback:
    """Test Kirk's fallback behavior without API key."""

    def test_fallback_without_api_key(self):
        """Test graceful degradation without API key."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure ANTHROPIC_API_KEY is not set
            os.environ.pop("ANTHROPIC_API_KEY", None)

            result = get_kirk_analysis(
                claim={"claim_id": "TEST-001"},
                rule_hits=[],
                fraud_score=0.5,
                decision_mode="recommendation",
            )

        assert "not available" in result["explanation"].lower()
        assert result["model"] == "none"
        assert result["tokens_used"] == 0
        assert result["agent"] == "Kirk"

    def test_fallback_includes_rule_hits(self):
        """Test fallback still includes rule hit descriptions."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)

            rule_hits = [
                RuleHit(
                    rule_id="TEST",
                    description="Test violation",
                    weight=0.1,
                    severity="low",
                    flag="test",
                ),
            ]

            result = get_kirk_analysis(
                claim={"claim_id": "TEST-001"},
                rule_hits=rule_hits,
                fraud_score=0.5,
                decision_mode="recommendation",
            )

        assert "Test violation" in result["risk_factors"]


class TestKirkResponseFormat:
    """Test expected Kirk response format."""

    def test_response_has_required_fields(self):
        """Verify response contains all required fields."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)

            result = get_kirk_analysis(
                claim={"claim_id": "TEST-001"},
                rule_hits=[],
                fraud_score=0.5,
                decision_mode="recommendation",
            )

        required_fields = [
            "explanation",
            "risk_factors",
            "recommendations",
            "model",
            "tokens_used",
            "agent",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_agent_field_is_kirk(self):
        """Verify agent field identifies Kirk."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)

            result = get_kirk_analysis(
                claim={"claim_id": "TEST-001"},
                rule_hits=[],
                fraud_score=0.5,
                decision_mode="recommendation",
            )

        assert result["agent"] == "Kirk"
