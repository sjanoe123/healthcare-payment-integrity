"""Embedding-based semantic field matching for healthcare claims.

This module provides PubMedBERT-based semantic similarity matching for
fields that don't match via direct alias lookup. It generates embeddings
for field names and finds the closest canonical OMOP CDM field matches.

Usage:
    matcher = EmbeddingMatcher()
    candidates = matcher.find_candidates("PatientMRN", top_k=5)
    # Returns: [("person_id", 0.85), ("visit_occurrence_id", 0.72), ...]
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from .omop_schema import OMOP_CLAIMS_SCHEMA

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Model options for healthcare terminology matching
# PubMedBERT variants are trained on biomedical literature
EMBEDDING_MODELS = {
    "pubmedbert": "pritamdeka/S-PubMedBert-MS-MARCO",
    "biobert": "dmis-lab/biobert-base-cased-v1.2",
    "minilm": "all-MiniLM-L6-v2",  # Faster, general-purpose fallback
}

# Default model - PubMedBERT for healthcare terminology
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "pubmedbert")

# Minimum similarity threshold for candidate consideration
MIN_SIMILARITY_THRESHOLD = 0.3

# Cache size for embedding computations
EMBEDDING_CACHE_SIZE = 1000


class EmbeddingMatcher:
    """Semantic field matcher using biomedical embeddings.

    Uses PubMedBERT (or configurable alternatives) to compute semantic
    similarity between source field names and canonical OMOP CDM fields.

    Attributes:
        model_name: The sentence transformer model to use
        _model: Lazy-loaded SentenceTransformer instance
        _canonical_embeddings: Pre-computed embeddings for OMOP fields
    """

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize the embedding matcher.

        Args:
            model_name: Model key from EMBEDDING_MODELS or full HuggingFace path.
                       Defaults to PubMedBERT variant.
        """
        self.model_name = model_name or DEFAULT_MODEL
        self._model: SentenceTransformer | None = None
        self._canonical_embeddings: NDArray[np.float32] | None = None
        self._canonical_fields: list[str] = []
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of model and canonical embeddings."""
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
            raise

        # Resolve model name
        model_path = EMBEDDING_MODELS.get(self.model_name, self.model_name)
        logger.info(f"Loading embedding model: {model_path}")

        self._model = SentenceTransformer(model_path)

        # Pre-compute embeddings for all canonical fields
        self._canonical_fields = list(OMOP_CLAIMS_SCHEMA.keys())

        # Create rich descriptions for better semantic matching
        field_descriptions = []
        for field_name in self._canonical_fields:
            field_def = OMOP_CLAIMS_SCHEMA[field_name]
            # Combine field name, description, and aliases for richer embedding
            desc_parts = [
                field_name.replace("_", " "),
                field_def.description,
            ]
            # Add a few key aliases
            if field_def.aliases:
                desc_parts.extend(
                    alias.replace("_", " ") for alias in field_def.aliases[:3]
                )
            field_descriptions.append(" | ".join(desc_parts))

        self._canonical_embeddings = self._model.encode(
            field_descriptions,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        self._initialized = True
        logger.info(
            f"Initialized EmbeddingMatcher with {len(self._canonical_fields)} canonical fields"
        )

    @lru_cache(maxsize=EMBEDDING_CACHE_SIZE)
    def _encode_field(self, field_name: str) -> tuple[float, ...]:
        """Encode a field name to embedding vector (cached).

        Args:
            field_name: Source field name to encode

        Returns:
            Tuple of embedding values (for hashability in cache)
        """
        self._ensure_initialized()

        # Normalize field name for better matching
        normalized = self._normalize_field_name(field_name)
        embedding = self._model.encode(  # type: ignore[union-attr]
            normalized,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return tuple(embedding.tolist())

    def find_candidates(
        self,
        source_field: str,
        top_k: int = 5,
        min_similarity: float = MIN_SIMILARITY_THRESHOLD,
    ) -> list[tuple[str, float]]:
        """Find top-k canonical field candidates for a source field.

        Args:
            source_field: Source field name to match
            top_k: Number of candidates to return
            min_similarity: Minimum cosine similarity threshold

        Returns:
            List of (canonical_field, similarity_score) tuples, sorted by score
        """
        self._ensure_initialized()

        # Get source embedding
        source_embedding = np.array(self._encode_field(source_field))

        # Compute cosine similarities
        similarities = self._cosine_similarity(
            source_embedding.reshape(1, -1),
            self._canonical_embeddings,
        )[0]

        # Get top-k indices above threshold
        candidates: list[tuple[str, float]] = []
        sorted_indices = np.argsort(similarities)[::-1]

        for idx in sorted_indices[:top_k]:
            score = float(similarities[idx])
            if score >= min_similarity:
                candidates.append((self._canonical_fields[idx], score))

        return candidates

    def find_best_match(
        self,
        source_field: str,
        min_similarity: float = MIN_SIMILARITY_THRESHOLD,
    ) -> tuple[str, float] | None:
        """Find the best matching canonical field.

        Args:
            source_field: Source field name to match
            min_similarity: Minimum similarity threshold

        Returns:
            Tuple of (canonical_field, score) or None if no match above threshold
        """
        candidates = self.find_candidates(
            source_field, top_k=1, min_similarity=min_similarity
        )
        return candidates[0] if candidates else None

    def batch_find_candidates(
        self,
        source_fields: list[str],
        top_k: int = 5,
        min_similarity: float = MIN_SIMILARITY_THRESHOLD,
    ) -> dict[str, list[tuple[str, float]]]:
        """Find candidates for multiple source fields efficiently.

        Args:
            source_fields: List of source field names
            top_k: Number of candidates per field
            min_similarity: Minimum similarity threshold

        Returns:
            Dictionary mapping source fields to their candidate lists
        """
        self._ensure_initialized()

        # Encode all source fields in batch
        normalized_fields = [self._normalize_field_name(f) for f in source_fields]
        source_embeddings = self._model.encode(  # type: ignore[union-attr]
            normalized_fields,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        # Compute all similarities at once
        all_similarities = self._cosine_similarity(
            source_embeddings,
            self._canonical_embeddings,
        )

        # Build results
        results: dict[str, list[tuple[str, float]]] = {}
        for i, source_field in enumerate(source_fields):
            similarities = all_similarities[i]
            sorted_indices = np.argsort(similarities)[::-1]

            candidates: list[tuple[str, float]] = []
            for idx in sorted_indices[:top_k]:
                score = float(similarities[idx])
                if score >= min_similarity:
                    candidates.append((self._canonical_fields[idx], score))

            results[source_field] = candidates

        return results

    @staticmethod
    def _normalize_field_name(field_name: str) -> str:
        """Normalize a field name for better embedding matching.

        Converts to human-readable form:
        - snake_case -> "snake case"
        - camelCase -> "camel Case"
        - Removes common prefixes/suffixes
        """
        import re

        # Handle camelCase
        result = re.sub(r"([a-z])([A-Z])", r"\1 \2", field_name)

        # Handle snake_case
        result = result.replace("_", " ")

        # Remove common prefixes/suffixes that don't add meaning
        prefixes = ["fld", "col", "txt", "num", "dt", "cd"]
        for prefix in prefixes:
            if result.lower().startswith(prefix + " "):
                result = result[len(prefix) + 1 :]

        return result.strip()

    @staticmethod
    def _cosine_similarity(
        a: NDArray[np.float32],
        b: NDArray[np.float32],
    ) -> NDArray[np.float32]:
        """Compute cosine similarity between vectors.

        Args:
            a: Query vectors (n_queries, embedding_dim)
            b: Reference vectors (n_refs, embedding_dim)

        Returns:
            Similarity matrix (n_queries, n_refs)
        """
        from sklearn.metrics.pairwise import cosine_similarity

        return cosine_similarity(a, b)


# Global singleton instance (lazy-loaded)
_matcher_instance: EmbeddingMatcher | None = None


def get_embedding_matcher() -> EmbeddingMatcher:
    """Get or create the global EmbeddingMatcher instance.

    Returns:
        Singleton EmbeddingMatcher instance
    """
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = EmbeddingMatcher()
    return _matcher_instance


def find_semantic_matches(
    source_field: str,
    top_k: int = 5,
    min_similarity: float = MIN_SIMILARITY_THRESHOLD,
) -> list[tuple[str, float]]:
    """Convenience function to find semantic matches for a field.

    Args:
        source_field: Source field name to match
        top_k: Number of candidates to return
        min_similarity: Minimum similarity threshold

    Returns:
        List of (canonical_field, similarity_score) tuples
    """
    matcher = get_embedding_matcher()
    return matcher.find_candidates(source_field, top_k, min_similarity)
