"""Claude API client for fraud analysis explanations."""
from __future__ import annotations

import json
import os
from typing import Any

import anthropic

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
        recommendations = ["Review flagged items for compliance", "Verify provider credentials"]

    return recommendations[:5]  # Limit to 5 recommendations
