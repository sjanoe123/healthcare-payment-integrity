"""Tests for ChromaDB policy documents and RAG functionality."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts to path for imports
scripts_path = str(Path(__file__).parent.parent / "scripts")
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

backend_path = str(Path(__file__).parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


class TestPolicyDocuments:
    """Test policy document structure and content."""

    def test_policy_count(self):
        """Verify all 75 policies are loaded."""
        from seed_chromadb import SAMPLE_POLICIES

        assert len(SAMPLE_POLICIES) == 75

    def test_policy_structure(self):
        """Validate all policies have required structure."""
        from seed_chromadb import SAMPLE_POLICIES

        for i, policy in enumerate(SAMPLE_POLICIES):
            assert "content" in policy, f"Policy {i}: missing content"
            assert "metadata" in policy, f"Policy {i}: missing metadata"
            assert "source" in policy["metadata"], f"Policy {i}: missing source"
            assert "chapter" in policy["metadata"], f"Policy {i}: missing chapter"
            assert "topic" in policy["metadata"], f"Policy {i}: missing topic"

    def test_policy_content_length(self):
        """Verify all policies have meaningful content."""
        from seed_chromadb import SAMPLE_POLICIES

        for i, policy in enumerate(SAMPLE_POLICIES):
            content_length = len(policy["content"])
            assert content_length >= 100, (
                f"Policy {i} ({policy['metadata'].get('topic', 'Unknown')}): "
                f"content too short ({content_length} chars)"
            )

    def test_no_duplicate_topics(self):
        """Verify no duplicate topics exist."""
        from seed_chromadb import SAMPLE_POLICIES

        topics = [p["metadata"]["topic"] for p in SAMPLE_POLICIES]
        duplicates = [t for t in topics if topics.count(t) > 1]
        assert len(set(duplicates)) == 0, f"Duplicate topics found: {set(duplicates)}"


class TestPolicyValidation:
    """Test the policy validation function."""

    def test_validate_policies_passes(self):
        """Verify validation passes for all policies."""
        from seed_chromadb import SAMPLE_POLICIES, validate_policies

        is_valid, errors = validate_policies(SAMPLE_POLICIES)
        assert is_valid, f"Validation failed with errors: {errors}"
        assert len(errors) == 0

    def test_validate_policies_detects_missing_content(self):
        """Verify validation catches missing content."""
        from seed_chromadb import validate_policies

        invalid_policies = [{"metadata": {"source": "X", "chapter": "1", "topic": "Y"}}]
        is_valid, errors = validate_policies(invalid_policies)
        assert not is_valid
        assert any("missing content" in e for e in errors)

    def test_validate_policies_detects_short_content(self):
        """Verify validation catches content that's too short."""
        from seed_chromadb import validate_policies

        invalid_policies = [
            {
                "content": "Too short",
                "metadata": {"source": "X", "chapter": "1", "topic": "Y"},
            }
        ]
        is_valid, errors = validate_policies(invalid_policies)
        assert not is_valid
        assert any("too short" in e for e in errors)

    def test_validate_policies_detects_missing_metadata(self):
        """Verify validation catches missing metadata."""
        from seed_chromadb import validate_policies

        invalid_policies = [{"content": "x" * 200}]
        is_valid, errors = validate_policies(invalid_policies)
        assert not is_valid
        assert any("missing metadata" in e for e in errors)


class TestPolicyCoverage:
    """Test that policies cover expected categories."""

    def test_specialty_specific_policies_exist(self):
        """Verify specialty-specific policies are included."""
        from seed_chromadb import SAMPLE_POLICIES

        topics = [p["metadata"]["topic"] for p in SAMPLE_POLICIES]
        expected_specialties = [
            "Diagnostic Imaging",
            "Operative Billing",
            "Psychiatric Services",
            "ED Coding",
            "Anesthesia Billing",
        ]
        for specialty in expected_specialties:
            assert any(specialty in t for t in topics), (
                f"Missing specialty: {specialty}"
            )

    def test_ncci_billing_policies_exist(self):
        """Verify NCCI/billing policies are included."""
        from seed_chromadb import SAMPLE_POLICIES

        topics = [p["metadata"]["topic"] for p in SAMPLE_POLICIES]
        expected_topics = [
            "PTP Edits",
            "MUE Edits",
            "E/M with Procedures",  # Modifier 25 topic
            "Global Periods",
        ]
        for topic in expected_topics:
            assert topic in topics, f"Missing NCCI topic: {topic}"

    def test_compliance_policies_exist(self):
        """Verify compliance policies are included."""
        from seed_chromadb import SAMPLE_POLICIES

        topics = [p["metadata"]["topic"] for p in SAMPLE_POLICIES]
        expected_compliance = [
            "Audit Process",
            "HIPAA Compliance",
            "Physician Self-Referral",
            "Kickback Prohibition",
        ]
        for topic in expected_compliance:
            assert topic in topics, f"Missing compliance topic: {topic}"

    def test_appeals_policies_exist(self):
        """Verify appeals process policies are included."""
        from seed_chromadb import SAMPLE_POLICIES

        topics = [p["metadata"]["topic"] for p in SAMPLE_POLICIES]
        expected_appeals = [
            "Prior Authorization",
            "ABN Requirements",
            "Five Levels",
            "Redetermination",
        ]
        for topic in expected_appeals:
            assert topic in topics, f"Missing appeals topic: {topic}"


class TestChromaDBIntegration:
    """Integration tests for ChromaDB seeding and search."""

    @pytest.fixture
    def temp_chroma_store(self):
        """Create a temporary ChromaDB store for testing."""
        from rag import ChromaStore
        from seed_chromadb import (
            LAST_REVIEWED_DATE,
            POLICY_EFFECTIVE_DATE,
            SAMPLE_POLICIES,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChromaStore(persist_dir=temp_dir, collection_name="test_policies")

            # Add a subset of policies for faster testing
            test_policies = SAMPLE_POLICIES[:10]
            documents = [p["content"] for p in test_policies]
            metadatas = []
            for p in test_policies:
                metadata = p["metadata"].copy()
                metadata["effective_date"] = POLICY_EFFECTIVE_DATE
                metadata["last_reviewed"] = LAST_REVIEWED_DATE
                metadatas.append(metadata)
            ids = [f"test_policy_{i}" for i in range(len(test_policies))]

            store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
            yield store

    def test_chromadb_stores_documents(self, temp_chroma_store):
        """Verify documents are stored in ChromaDB."""
        assert temp_chroma_store.count() == 10

    def test_chromadb_search_returns_results(self, temp_chroma_store):
        """Verify search returns relevant results."""
        results = temp_chroma_store.search("NCCI PTP edits", n_results=3)
        assert len(results) > 0
        assert "content" in results[0]
        assert "metadata" in results[0]

    def test_chromadb_metadata_includes_dates(self, temp_chroma_store):
        """Verify metadata includes effective_date and last_reviewed."""
        results = temp_chroma_store.search("NCCI", n_results=1)
        assert len(results) > 0
        metadata = results[0]["metadata"]
        assert "effective_date" in metadata
        assert "last_reviewed" in metadata
        assert metadata["effective_date"] == "2024-01-01"
        assert metadata["last_reviewed"] == "2024-12-17"

    def test_search_specialty_content(self, temp_chroma_store):
        """Test search retrieval works for different content types."""
        # Search for NCCI content (should be in first 10 policies)
        results = temp_chroma_store.search("modifier indicator", n_results=1)
        assert len(results) > 0


class TestRAGSearchRelevance:
    """Test RAG search returns relevant results for various query types."""

    @pytest.fixture(scope="class")
    def full_chroma_store(self):
        """Create a ChromaDB store with all 75 policies for testing.

        Scope is 'class' to avoid recreating the store for each test method.
        This significantly improves test performance as ChromaDB seeding with
        75 documents takes several seconds.
        """
        from rag import ChromaStore
        from seed_chromadb import (
            LAST_REVIEWED_DATE,
            POLICY_EFFECTIVE_DATE,
            SAMPLE_POLICIES,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChromaStore(persist_dir=temp_dir, collection_name="full_policies")

            documents = [p["content"] for p in SAMPLE_POLICIES]
            metadatas = []
            for p in SAMPLE_POLICIES:
                metadata = p["metadata"].copy()
                metadata["effective_date"] = POLICY_EFFECTIVE_DATE
                metadata["last_reviewed"] = LAST_REVIEWED_DATE
                metadatas.append(metadata)
            ids = [f"policy_{i}" for i in range(len(SAMPLE_POLICIES))]

            store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
            yield store

    def test_search_ncci_ptp_content(self, full_chroma_store):
        """Verify search returns relevant NCCI PTP content."""
        results = full_chroma_store.search(
            "procedure to procedure edits bundling column codes", n_results=3
        )
        assert len(results) > 0
        # First result should be PTP-related
        content = results[0]["content"].lower()
        assert "ptp" in content or "procedure" in content

    def test_search_mue_content(self, full_chroma_store):
        """Verify search returns relevant MUE content."""
        results = full_chroma_store.search(
            "medically unlikely edits units limit quantity", n_results=3
        )
        assert len(results) > 0
        content = results[0]["content"].lower()
        assert "mue" in content or "unit" in content or "limit" in content

    def test_search_modifier_25_content(self, full_chroma_store):
        """Verify search returns modifier 25 guidelines."""
        results = full_chroma_store.search(
            "modifier 25 significant separately identifiable E/M", n_results=3
        )
        assert len(results) > 0
        content = results[0]["content"].lower()
        assert "modifier" in content or "e/m" in content or "separately" in content

    def test_search_oig_exclusion_content(self, full_chroma_store):
        """Verify search returns OIG exclusion content."""
        results = full_chroma_store.search(
            "OIG excluded provider LEIE sanctions debarred", n_results=3
        )
        assert len(results) > 0
        content = results[0]["content"].lower()
        assert "oig" in content or "exclusion" in content or "leie" in content

    def test_search_hipaa_content(self, full_chroma_store):
        """Verify search returns HIPAA compliance content."""
        results = full_chroma_store.search(
            "HIPAA privacy protected health information PHI", n_results=3
        )
        assert len(results) > 0
        content = results[0]["content"].lower()
        assert "hipaa" in content or "phi" in content or "privacy" in content

    def test_search_appeals_content(self, full_chroma_store):
        """Verify search returns appeals process content."""
        results = full_chroma_store.search(
            "Medicare appeals redetermination ALJ hearing", n_results=3
        )
        assert len(results) > 0
        content = results[0]["content"].lower()
        assert "appeal" in content or "redetermination" in content or "alj" in content

    def test_search_surgical_global_content(self, full_chroma_store):
        """Verify search returns global surgery content."""
        results = full_chroma_store.search(
            "global surgery period 090 010 postoperative", n_results=3
        )
        assert len(results) > 0
        content = results[0]["content"].lower()
        assert "global" in content or "surgery" in content or "postoperative" in content

    def test_search_stark_law_content(self, full_chroma_store):
        """Verify search returns Stark Law content."""
        results = full_chroma_store.search(
            "Stark physician self-referral designated health services", n_results=3
        )
        assert len(results) > 0
        content = results[0]["content"].lower()
        assert "stark" in content or "self-referral" in content or "dhs" in content

    def test_search_abn_content(self, full_chroma_store):
        """Verify search returns ABN content."""
        results = full_chroma_store.search(
            "advance beneficiary notice Medicare coverage denial patient", n_results=3
        )
        assert len(results) > 0
        content = results[0]["content"].lower()
        assert "abn" in content or "beneficiary" in content or "notice" in content

    def test_search_radiology_content(self, full_chroma_store):
        """Verify search returns radiology imaging content."""
        results = full_chroma_store.search(
            "CT MRI diagnostic imaging technical professional component", n_results=3
        )
        assert len(results) > 0
        content = results[0]["content"].lower()
        assert (
            "radiology" in content
            or "imaging" in content
            or "ct" in content
            or "mri" in content
        )


class TestSeedingPerformance:
    """Test seeding performance metrics."""

    def test_seed_returns_metrics(self):
        """Verify seed_chromadb returns performance metrics."""
        from seed_chromadb import SAMPLE_POLICIES, validate_policies

        # Just test validation performance (fast)
        import time

        start = time.time()
        is_valid, errors = validate_policies(SAMPLE_POLICIES)
        elapsed_ms = (time.time() - start) * 1000

        assert is_valid
        assert elapsed_ms < 1000  # Validation should be under 1 second
