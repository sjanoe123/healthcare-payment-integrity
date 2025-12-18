#!/usr/bin/env python
"""
Manual integration tests for Kirk - requires ANTHROPIC_API_KEY.

Run manually:
    python scripts/test_kirk_live.py

NOT included in CI/CD - API calls cost money and require key.

Prerequisites:
    - ANTHROPIC_API_KEY environment variable set
    - Or .env file with the key in the project root
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = str(Path(__file__).parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Load .env file if it exists
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

from kirk_config import KIRK_CONFIG
from claude_client import get_kirk_analysis
from rules import RuleHit


def check_api_key():
    """Verify API key is available."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("\nSet it via:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        print("  OR")
        print("  Create .env file with ANTHROPIC_API_KEY=your-key-here")
        sys.exit(1)
    print(f"API Key: {api_key[:20]}...{api_key[-4:]}")
    return True


def test_kirk_analyzes_clean_claim():
    """Test Kirk with a clean claim (no violations)."""
    print("\n" + "=" * 60)
    print("TEST 1: Clean Claim Analysis")
    print("=" * 60)

    claim = {
        "claim_id": "CLEAN-001",
        "billed_amount": 130.00,
        "diagnosis_codes": ["J06.9"],  # Common cold
        "items": [
            {
                "procedure_code": "99214",
                "diagnosis_code": "J06.9",
                "quantity": 1,
                "line_amount": 130.00,
            },
        ],
        "provider": {
            "npi": "9999999999",
            "specialty": "family medicine",
        },
        "member": {"age": 35, "gender": "M"},
    }

    result = get_kirk_analysis(
        claim=claim,
        rule_hits=[],
        fraud_score=0.3,
        decision_mode="informational",
        config=KIRK_CONFIG,
    )

    print(f"\nModel: {result['model']}")
    print(f"Tokens: {result['tokens_used']}")
    print(f"Agent: {result['agent']}")
    print(f"\n--- Kirk's Analysis ---\n{result['explanation']}")
    print(f"\n--- Recommendations ---")
    for rec in result["recommendations"]:
        print(f"  - {rec}")

    assert result["model"] == KIRK_CONFIG.model, "Wrong model used"
    assert result["agent"] == "Kirk", "Agent not identified as Kirk"
    assert result["tokens_used"] > 0, "No tokens used"
    print("\n PASSED")


def test_kirk_with_high_risk_claim():
    """Test Kirk identifies multiple fraud indicators."""
    print("\n" + "=" * 60)
    print("TEST 2: High Risk Claim Analysis")
    print("=" * 60)

    claim = {
        "claim_id": "HIGH-RISK-001",
        "billed_amount": 5000.00,
        "diagnosis_codes": ["M54.5", "J06.9"],
        "items": [
            {
                "procedure_code": "99215",
                "diagnosis_code": "M54.5",
                "quantity": 1,
                "line_amount": 200.00,
            },
            {
                "procedure_code": "99214",
                "diagnosis_code": "J06.9",
                "quantity": 1,
                "line_amount": 150.00,
            },
            {
                "procedure_code": "99213",
                "diagnosis_code": "M54.5",
                "quantity": 5,  # Excessive quantity
                "line_amount": 4650.00,
            },
        ],
        "provider": {
            "npi": "1234567890",  # Known excluded NPI
            "specialty": "pain management",
        },
        "member": {"age": 45, "gender": "F"},
    }

    rule_hits = [
        RuleHit(
            rule_id="OIG_EXCLUSION",
            description="Provider NPI 1234567890 found on OIG LEIE exclusion list",
            weight=0.5,
            severity="critical",
            flag="provider",
            citation="42 CFR 1001.1901",
        ),
        RuleHit(
            rule_id="NCCI_PTP",
            description="PTP edit between 99214 and 99215",
            weight=0.2,
            severity="high",
            flag="ncci",
            citation="NCCI Policy Manual Ch. 1",
        ),
        RuleHit(
            rule_id="NCCI_MUE",
            description="99213 quantity 5 exceeds MUE limit of 1",
            weight=0.15,
            severity="high",
            flag="ncci",
            citation="NCCI MUE Table",
        ),
        RuleHit(
            rule_id="HIGH_DOLLAR",
            description="Claim amount $5000 exceeds threshold",
            weight=0.1,
            severity="medium",
            flag="financial",
        ),
    ]

    rag_context = """[NCCI Policy Manual]: NCCI Procedure-to-Procedure (PTP) Edits define pairs of HCPCS/CPT codes that should not be reported together. Column 1 code is the comprehensive code, column 2 is the component code. Modifier indicator determines if a modifier can bypass the edit.

[OIG Compliance]: Providers on the OIG LEIE exclusion list are prohibited from participating in federal healthcare programs. Claims from excluded providers should be denied and referred for further investigation per 42 CFR 1001."""

    result = get_kirk_analysis(
        claim=claim,
        rule_hits=rule_hits,
        fraud_score=0.85,
        decision_mode="soft_hold",
        rag_context=rag_context,
        config=KIRK_CONFIG,
    )

    print(f"\nModel: {result['model']}")
    print(f"Tokens: {result['tokens_used']}")
    print(f"Agent: {result['agent']}")
    print(f"\n--- Kirk's Analysis ---\n{result['explanation']}")
    print(f"\n--- Recommendations ---")
    for rec in result["recommendations"]:
        print(f"  - {rec}")
    print(f"\n--- Risk Factors ---")
    for factor in result["risk_factors"]:
        print(f"  - {factor}")

    assert result["model"] == KIRK_CONFIG.model, "Wrong model used"
    assert result["agent"] == "Kirk", "Agent not identified as Kirk"
    assert result["tokens_used"] > 0, "No tokens used"
    assert len(result["risk_factors"]) >= 4, "Missing risk factors"
    print("\n PASSED")


def test_kirk_response_format():
    """Verify Kirk returns citations and recommendations."""
    print("\n" + "=" * 60)
    print("TEST 3: Response Format Validation")
    print("=" * 60)

    claim = {
        "claim_id": "FORMAT-001",
        "billed_amount": 300.00,
        "items": [
            {
                "procedure_code": "99214",
                "quantity": 1,
                "line_amount": 300.00,
            },
        ],
        "provider": {"npi": "5555555555"},
    }

    rule_hits = [
        RuleHit(
            rule_id="REIMB_OUTLIER",
            description="Billed amount $300 exceeds MPFS benchmark of $130",
            weight=0.2,
            severity="medium",
            flag="financial",
            citation="MPFS Payment Policy",
        ),
    ]

    result = get_kirk_analysis(
        claim=claim,
        rule_hits=rule_hits,
        fraud_score=0.6,
        decision_mode="recommendation",
        config=KIRK_CONFIG,
    )

    print(f"\nModel: {result['model']}")
    print(f"Tokens: {result['tokens_used']}")
    print(f"\n--- Kirk's Analysis ---\n{result['explanation']}")

    # Check response structure
    explanation = result["explanation"].lower()

    # Kirk should include structured sections
    checks = {
        "has_summary": any(
            word in explanation for word in ["summary", "risk", "assessment"]
        ),
        "has_findings": any(word in explanation for word in ["finding", "issue", "concern"]),
        "has_recommendations": len(result["recommendations"]) > 0,
        "has_agent": result["agent"] == "Kirk",
    }

    print(f"\n--- Format Checks ---")
    for check, passed in checks.items():
        status = "" if passed else ""
        print(f"  {status} {check}: {passed}")

    assert all(checks.values()), f"Format checks failed: {checks}"
    print("\n PASSED")


def main():
    """Run all Kirk live tests."""
    print("=" * 60)
    print("KIRK LIVE INTEGRATION TESTS")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Name: {KIRK_CONFIG.name}")
    print(f"  Model: {KIRK_CONFIG.model}")
    print(f"  Max Tokens: {KIRK_CONFIG.max_tokens}")
    print(f"  Temperature: {KIRK_CONFIG.temperature}")

    check_api_key()

    tests = [
        test_kirk_analyzes_clean_claim,
        test_kirk_with_high_risk_claim,
        test_kirk_response_format,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    print("\n All Kirk live tests passed!")


if __name__ == "__main__":
    main()
