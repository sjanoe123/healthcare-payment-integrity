"""Claude API client for fraud analysis explanations.

This module provides two analysis functions:
- get_kirk_analysis: Uses Kirk persona with Claude Sonnet 4.5 (recommended)
- get_fraud_explanation: Legacy function using Claude 3 Haiku (deprecated)
"""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from kirk_config import KIRK_CONFIG, KIRK_SYSTEM_PROMPT, KirkConfig
from rules import RuleHit


def format_rule_hits(hits: list[RuleHit]) -> str:
    """Format rule hits for the prompt."""
    if not hits:
        return "No rule violations detected."

    lines = []
    for hit in hits:
        lines.append(f"- [{hit.severity.upper()}] {hit.rule_id}: {hit.description}")
        if hit.citation:
            lines.append(f"  Citation: {hit.citation}")

    return "\n".join(lines)


def get_fraud_explanation(
    claim: dict[str, Any],
    rule_hits: list[RuleHit],
    fraud_score: float,
    decision_mode: str,
    rag_context: str | None = None,
) -> dict[str, Any]:
    """Get Claude's analysis and explanation of the fraud risk."""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "explanation": "Claude API key not configured. Rule-based analysis only.",
            "risk_factors": [h.description for h in rule_hits],
            "recommendations": ["Review flagged items manually"],
            "model": "none",
            "tokens_used": 0,
        }

    client = anthropic.Anthropic(api_key=api_key)

    # Build the prompt
    claim_summary = json.dumps(claim, indent=2, default=str)
    rule_summary = format_rule_hits(rule_hits)

    context_section = ""
    if rag_context:
        context_section = f"""
## Relevant Policy Context
{rag_context}
"""

    prompt = f"""You are a healthcare payment integrity analyst. Analyze this claim for potential fraud, waste, and abuse (FWA).

## Claim Data
```json
{claim_summary}
```

## Rule Violations Detected
{rule_summary}

## Current Assessment
- Fraud Score: {fraud_score:.2f} (0 = lowest risk, 1 = highest risk)
- Decision Mode: {decision_mode}
{context_section}
## Your Task
Provide a concise analysis including:
1. A 2-3 sentence summary of the fraud risk
2. Key risk factors identified (bullet points)
3. Recommended actions for the investigator

Be specific and cite the relevant rules or policies. Keep the response under 300 words."""

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",  # Most cost-effective
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text if response.content else ""

        return {
            "explanation": content,
            "risk_factors": [h.description for h in rule_hits],
            "recommendations": extract_recommendations(content),
            "model": "claude-3-haiku-20240307",
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
        }

    except anthropic.APIError as e:
        return {
            "explanation": f"Claude API error: {str(e)}. Using rule-based analysis only.",
            "risk_factors": [h.description for h in rule_hits],
            "recommendations": ["Review flagged items manually"],
            "model": "error",
            "tokens_used": 0,
        }


def extract_recommendations(text: str) -> list[str]:
    """Extract recommendations from Claude's response."""
    recommendations = []

    # Look for numbered or bulleted recommendations
    lines = text.split("\n")
    in_recommendations = False

    for line in lines:
        line = line.strip()
        if "recommend" in line.lower() or "action" in line.lower():
            in_recommendations = True
            continue

        if in_recommendations:
            if line.startswith(("-", "*", "1", "2", "3", "4", "5")):
                # Clean up the line
                cleaned = line.lstrip("-*0123456789. ")
                if cleaned:
                    recommendations.append(cleaned)
            elif not line:
                # Empty line might end the section
                if recommendations:
                    break

    # Fallback if no recommendations found
    if not recommendations:
        recommendations = [
            "Review flagged items for compliance",
            "Verify provider credentials",
        ]

    return recommendations[:5]  # Limit to 5 recommendations


def build_kirk_prompt(
    claim: dict[str, Any],
    rule_hits: list[RuleHit],
    fraud_score: float,
    decision_mode: str,
    rag_context: str | None = None,
) -> str:
    """Build the user prompt for Kirk's analysis.

    This function constructs the detailed prompt that Kirk will analyze,
    including claim data, rule violations, and relevant policy context.

    Args:
        claim: The claim data dictionary
        rule_hits: List of rule violations detected
        fraud_score: Calculated fraud score (0.0-1.0)
        decision_mode: The decision mode based on score thresholds
        rag_context: Optional policy context from RAG retrieval

    Returns:
        Formatted prompt string for Kirk's analysis
    """
    claim_summary = json.dumps(claim, indent=2, default=str)
    rule_summary = format_rule_hits(rule_hits)

    context_section = ""
    if rag_context:
        context_section = f"""
## Relevant Policy Context
{rag_context}
"""

    return f"""Analyze this healthcare claim for potential fraud, waste, and abuse (FWA).

## Claim Data
```json
{claim_summary}
```

## Rule Violations Detected
{rule_summary}

## Current Assessment
- Fraud Score: {fraud_score:.2f} (0 = lowest risk, 1 = highest risk)
- Decision Mode: {decision_mode}
{context_section}
Provide your expert analysis following the response format specified in your instructions."""


def get_kirk_analysis(
    claim: dict[str, Any],
    rule_hits: list[RuleHit],
    fraud_score: float,
    decision_mode: str,
    rag_context: str | None = None,
    config: KirkConfig | None = None,
) -> dict[str, Any]:
    """Get Kirk's expert analysis of the claim.

    Kirk is an expert Healthcare Payment Integrity Auditor persona
    powered by Claude Sonnet 4.5. He provides formal, thorough analysis
    with regulatory citations and prioritized recommendations.

    Args:
        claim: The claim data dictionary
        rule_hits: List of rule violations detected
        fraud_score: Calculated fraud score (0.0-1.0)
        decision_mode: The decision mode based on score thresholds
        rag_context: Optional policy context from RAG retrieval
        config: Optional Kirk configuration (uses KIRK_CONFIG if not provided)

    Returns:
        Dictionary containing:
        - explanation: Kirk's detailed analysis
        - risk_factors: List of identified risk factors
        - recommendations: Prioritized action items
        - model: The Claude model used
        - tokens_used: Total tokens consumed
        - agent: "Kirk" identifier
    """
    if config is None:
        config = KIRK_CONFIG

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "explanation": (
                "Kirk is not available - Anthropic API key not configured. "
                "Rule-based analysis only."
            ),
            "risk_factors": [h.description for h in rule_hits],
            "recommendations": ["Review flagged items manually"],
            "model": "none",
            "tokens_used": 0,
            "agent": config.name,
        }

    client = anthropic.Anthropic(api_key=api_key)

    # Build the prompt for Kirk
    user_prompt = build_kirk_prompt(
        claim=claim,
        rule_hits=rule_hits,
        fraud_score=fraud_score,
        decision_mode=decision_mode,
        rag_context=rag_context,
    )

    try:
        response = client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            system=KIRK_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text if response.content else ""

        return {
            "explanation": content,
            "risk_factors": [h.description for h in rule_hits],
            "recommendations": extract_recommendations(content)[
                : config.max_recommendations
            ],
            "model": config.model,
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
            "agent": config.name,
        }

    except anthropic.APIError as e:
        return {
            "explanation": f"Kirk encountered an API error: {e!s}. Using rule-based analysis only.",
            "risk_factors": [h.description for h in rule_hits],
            "recommendations": ["Review flagged items manually"],
            "model": "error",
            "tokens_used": 0,
            "agent": config.name,
        }
