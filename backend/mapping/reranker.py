"""LLM reranker for semantic field mapping using Claude Haiku 4.5.

This module provides confidence scoring and reranking of embedding-based
field mapping candidates using Claude Haiku for cost-effective inference.

Usage:
    reranker = MappingReranker()
    result = reranker.rerank(
        source_field="PatientMRN",
        candidates=[("person_id", 0.85), ("visit_occurrence_id", 0.72)],
        sample_values=["MRN-12345", "MRN-67890"]
    )
    # Returns: {"target_field": "person_id", "confidence": 92, "reasoning": "..."}
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Claude Haiku 4.5 for cost-effective reranking
# ~25x cheaper than Sonnet ($0.25/M vs $3/M input)
RERANKER_MODEL = "claude-haiku-4-5-20250514"

# Confidence thresholds for routing decisions
HIGH_CONFIDENCE_THRESHOLD = 85  # Auto-accept
LOW_CONFIDENCE_THRESHOLD = 50  # Route to human review


@dataclass
class RerankerResult:
    """Result from LLM reranking."""

    target_field: str
    confidence: int  # 0-100
    reasoning: str
    source_field: str
    embedding_score: float
    model: str
    tokens_used: int

    def needs_review(self) -> bool:
        """Check if this mapping needs human review."""
        return self.confidence < HIGH_CONFIDENCE_THRESHOLD

    def is_low_confidence(self) -> bool:
        """Check if this is a low-confidence mapping."""
        return self.confidence < LOW_CONFIDENCE_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "target_field": self.target_field,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "source_field": self.source_field,
            "embedding_score": self.embedding_score,
            "needs_review": self.needs_review(),
            "model": self.model,
            "tokens_used": self.tokens_used,
        }


class MappingReranker:
    """LLM-based reranker for field mapping candidates.

    Uses Claude Haiku 4.5 to rerank embedding candidates and provide
    confidence scores with reasoning. Haiku is ideal for this task:
    - Structured selection from pre-filtered candidates
    - Small context window needed
    - ~25x cheaper than Sonnet
    - Fast response time for interactive workflows
    """

    def __init__(
        self,
        model: str = RERANKER_MODEL,
        high_confidence_threshold: int = HIGH_CONFIDENCE_THRESHOLD,
        low_confidence_threshold: int = LOW_CONFIDENCE_THRESHOLD,
    ) -> None:
        """Initialize the reranker.

        Args:
            model: Claude model to use for reranking
            high_confidence_threshold: Score above which to auto-accept
            low_confidence_threshold: Score below which to flag for review
        """
        self.model = model
        self.high_confidence_threshold = high_confidence_threshold
        self.low_confidence_threshold = low_confidence_threshold
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy-load the Anthropic client."""
        if self._client is None:
            try:
                import anthropic

                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY not set")
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError("anthropic package not installed")
        return self._client

    def rerank(
        self,
        source_field: str,
        candidates: list[tuple[str, float]],
        sample_values: list[Any] | None = None,
        field_context: dict[str, str] | None = None,
    ) -> RerankerResult | None:
        """Rerank candidates using Claude Haiku.

        Args:
            source_field: The source field name to map
            candidates: List of (canonical_field, embedding_score) tuples
            sample_values: Optional sample values from the source field
            field_context: Optional context about canonical fields

        Returns:
            RerankerResult with best match and confidence, or None on error
        """
        if not candidates:
            return None

        # Format candidates for the prompt
        candidates_text = "\n".join(
            f"{i + 1}. {field} (embedding similarity: {score:.3f})"
            for i, (field, score) in enumerate(candidates)
        )

        # Format sample values
        samples_text = "No sample values provided"
        if sample_values:
            # Limit to 5 samples and truncate long values
            truncated = [str(v)[:50] for v in sample_values[:5]]
            samples_text = ", ".join(f'"{v}"' for v in truncated)

        prompt = f"""You are a healthcare data mapping expert. Your task is to select the best OMOP CDM field mapping.

## Source Field
Name: "{source_field}"
Sample values: {samples_text}

## Candidate Mappings (from embedding similarity)
{candidates_text}

## OMOP CDM Context
The target schema is OMOP CDM (Observational Medical Outcomes Partnership Common Data Model) used for healthcare analytics. Key field categories:
- person_id: Patient/member identifier
- visit_*: Encounter/visit information
- procedure_*: Procedure codes and details
- condition_*: Diagnosis codes
- provider_id, npi: Provider identifiers
- *_date, *_datetime: Temporal fields
- *_source_value: Original source values

## Instructions
1. Analyze the source field name and sample values
2. Consider healthcare domain conventions
3. Select the BEST matching candidate
4. Provide confidence score (0-100) based on:
   - Name similarity
   - Value format alignment
   - Healthcare domain knowledge
   - Semantic meaning match

Respond with ONLY valid JSON:
{{"target_field": "selected_field_name", "confidence": 85, "reasoning": "Brief explanation of why this mapping is correct"}}"""

        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=200,
                temperature=0,  # Deterministic for consistency
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text if response.content else ""
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            # Parse the JSON response
            result = self._parse_response(content)
            if not result:
                logger.warning(f"Failed to parse reranker response for {source_field}")
                return None

            # Find the embedding score for the selected field
            embedding_score = 0.0
            for field, score in candidates:
                if field == result["target_field"]:
                    embedding_score = score
                    break

            return RerankerResult(
                target_field=result["target_field"],
                confidence=result["confidence"],
                reasoning=result["reasoning"],
                source_field=source_field,
                embedding_score=embedding_score,
                model=self.model,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error(f"Reranker error for {source_field}: {e}")
            return None

    def batch_rerank(
        self,
        mappings: list[dict[str, Any]],
    ) -> list[RerankerResult | None]:
        """Rerank multiple field mappings.

        Args:
            mappings: List of dicts with keys:
                - source_field: str
                - candidates: list[tuple[str, float]]
                - sample_values: list[Any] (optional)

        Returns:
            List of RerankerResult objects (None for failed mappings)
        """
        results = []
        for mapping in mappings:
            result = self.rerank(
                source_field=mapping["source_field"],
                candidates=mapping["candidates"],
                sample_values=mapping.get("sample_values"),
            )
            results.append(result)
        return results

    def _parse_response(self, text: str) -> dict[str, Any] | None:
        """Parse JSON response from Claude.

        Args:
            text: Raw response text

        Returns:
            Parsed dict or None if parsing fails
        """
        if not text:
            return None

        # Try to find JSON in markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try to parse as raw JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try to find JSON object pattern
        json_match = re.search(r"\{[^{}]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None


# Global singleton instance (lazy-loaded)
_reranker_instance: MappingReranker | None = None


def get_reranker() -> MappingReranker:
    """Get or create the global MappingReranker instance.

    Returns:
        Singleton MappingReranker instance
    """
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = MappingReranker()
    return _reranker_instance


def rerank_mapping(
    source_field: str,
    candidates: list[tuple[str, float]],
    sample_values: list[Any] | None = None,
) -> RerankerResult | None:
    """Convenience function to rerank field mapping candidates.

    Args:
        source_field: Source field name
        candidates: List of (canonical_field, score) tuples
        sample_values: Optional sample values

    Returns:
        RerankerResult or None on error
    """
    reranker = get_reranker()
    return reranker.rerank(source_field, candidates, sample_values)
