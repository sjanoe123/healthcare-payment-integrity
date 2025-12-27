"""Tests for policy versioning functionality."""

import pytest
import tempfile
import shutil

from rag.chroma_store import (
    ChromaStore,
    _compute_content_hash,
    _increment_version,
)


class TestVersionHelpers:
    """Test helper functions for versioning."""

    def test_compute_content_hash(self):
        """Should compute consistent hash for same content."""
        content = "This is a test policy document."
        hash1 = _compute_content_hash(content)
        hash2 = _compute_content_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated to 16 chars

    def test_compute_content_hash_different_content(self):
        """Different content should produce different hashes."""
        hash1 = _compute_content_hash("Document version 1")
        hash2 = _compute_content_hash("Document version 2")

        assert hash1 != hash2

    def test_increment_version_simple(self):
        """Should increment simple version numbers."""
        assert _increment_version("1") == "2"
        assert _increment_version("5") == "6"
        assert _increment_version("99") == "100"

    def test_increment_version_dotted(self):
        """Should increment last component of dotted versions."""
        assert _increment_version("1.0") == "1.1"
        assert _increment_version("2024.1") == "2024.2"
        assert _increment_version("1.2.3") == "1.2.4"

    def test_increment_version_none(self):
        """Should return '1' for None input."""
        assert _increment_version(None) == "1"

    def test_increment_version_empty(self):
        """Should return '1' for empty string."""
        assert _increment_version("") == "1"


class TestPolicyVersioning:
    """Test ChromaStore versioning methods."""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary ChromaStore for testing."""
        temp_dir = tempfile.mkdtemp()
        store = ChromaStore(persist_dir=temp_dir, collection_name="test_policies")
        yield store
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_add_first_version(self, temp_store):
        """Adding first version should get version 1."""
        result = temp_store.add_document_with_version(
            document="This is the first version of the policy.",
            metadata={"source": "LCD", "effective_date": "2024-01-01"},
            policy_key="LCD-L12345",
        )

        assert result["version"] == "1"
        assert result["is_duplicate"] is False
        assert result["document_id"] == "LCD-L12345_v1"
        assert temp_store.count() == 1

    def test_add_second_version(self, temp_store):
        """Adding second version should increment version number."""
        # Add first version
        temp_store.add_document_with_version(
            document="First version content.",
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
        )

        # Add second version
        result = temp_store.add_document_with_version(
            document="Second version with different content.",
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
        )

        assert result["version"] == "2"
        assert result["document_id"] == "LCD-L12345_v2"
        assert temp_store.count() == 2

    def test_duplicate_content_detection(self, temp_store):
        """Should detect duplicate content and not add again."""
        content = "This is the exact same policy content."

        # Add first time
        result1 = temp_store.add_document_with_version(
            document=content,
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
        )
        assert result1["is_duplicate"] is False

        # Add same content again
        result2 = temp_store.add_document_with_version(
            document=content,
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
        )
        assert result2["is_duplicate"] is True
        assert result2["document_id"] == result1["document_id"]
        assert temp_store.count() == 1  # No new document added

    def test_replace_existing(self, temp_store):
        """Replace mode should mark old version as not current."""
        # Add first version
        temp_store.add_document_with_version(
            document="Version 1 content.",
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
        )

        # Add second version with replace
        result = temp_store.add_document_with_version(
            document="Version 2 content - replaced.",
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
            replace_existing=True,
        )

        assert result["replaced_id"] == "LCD-L12345_v1"
        assert result["version"] == "2"

        # Check that old version is marked as not current
        versions = temp_store.get_document_versions("LCD-L12345")
        v1 = next(v for v in versions if v["id"] == "LCD-L12345_v1")
        v2 = next(v for v in versions if v["id"] == "LCD-L12345_v2")

        assert v1["metadata"]["is_current"] is False
        assert v2["metadata"]["is_current"] is True

    def test_get_document_versions(self, temp_store):
        """Should return all versions sorted by version descending."""
        # Add multiple versions
        for i in range(1, 4):
            temp_store.add_document_with_version(
                document=f"Version {i} content.",
                metadata={"source": "LCD"},
                policy_key="LCD-L12345",
            )

        versions = temp_store.get_document_versions("LCD-L12345")

        assert len(versions) == 3
        # Should be sorted newest first
        assert versions[0]["metadata"]["version"] == "3"
        assert versions[1]["metadata"]["version"] == "2"
        assert versions[2]["metadata"]["version"] == "1"

    def test_get_document_versions_with_content(self, temp_store):
        """Should include content when requested."""
        temp_store.add_document_with_version(
            document="Policy content here.",
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
        )

        versions = temp_store.get_document_versions("LCD-L12345", include_content=True)

        assert len(versions) == 1
        assert "content" in versions[0]
        assert versions[0]["content"] == "Policy content here."

    def test_get_document_versions_nonexistent(self, temp_store):
        """Should return empty list for nonexistent policy key."""
        versions = temp_store.get_document_versions("NONEXISTENT-KEY")
        assert versions == []

    def test_get_latest_version(self, temp_store):
        """Should return the latest/current version."""
        for i in range(1, 4):
            temp_store.add_document_with_version(
                document=f"Version {i} content.",
                metadata={"source": "LCD"},
                policy_key="LCD-L12345",
                replace_existing=True,
            )

        latest = temp_store.get_latest_version("LCD-L12345")

        assert latest is not None
        assert latest["metadata"]["version"] == "3"
        assert latest["metadata"]["is_current"] is True

    def test_get_latest_version_nonexistent(self, temp_store):
        """Should return None for nonexistent policy key."""
        latest = temp_store.get_latest_version("NONEXISTENT-KEY")
        assert latest is None

    def test_list_policy_keys(self, temp_store):
        """Should list all unique policy keys."""
        # Add documents with different policy keys
        temp_store.add_document_with_version(
            document="LCD policy content.",
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
        )
        temp_store.add_document_with_version(
            document="NCCI policy content.",
            metadata={"source": "NCCI"},
            policy_key="NCCI-PTP-001",
        )
        temp_store.add_document_with_version(
            document="Another LCD policy.",
            metadata={"source": "LCD"},
            policy_key="LCD-L67890",
        )

        keys = temp_store.list_policy_keys()

        assert len(keys) == 3
        assert "LCD-L12345" in keys
        assert "LCD-L67890" in keys
        assert "NCCI-PTP-001" in keys

    def test_get_version_history(self, temp_store):
        """Should return version history summary."""
        for i in range(1, 3):
            temp_store.add_document_with_version(
                document=f"Version {i} content.",
                metadata={
                    "source": "LCD",
                    "effective_date": f"2024-0{i}-01",
                },
                policy_key="LCD-L12345",
                replace_existing=True,
            )

        history = temp_store.get_version_history("LCD-L12345")

        assert len(history) == 2
        # Newest first
        assert history[0]["version"] == "2"
        assert history[0]["is_current"] is True
        assert history[0]["effective_date"] == "2024-02-01"
        assert history[1]["version"] == "1"
        assert history[1]["is_current"] is False

    def test_metadata_preserved(self, temp_store):
        """Should preserve all metadata fields."""
        temp_store.add_document_with_version(
            document="Policy with full metadata.",
            metadata={
                "source": "LCD",
                "document_type": "guideline",
                "effective_date": "2024-01-01",
                "expires_date": "2025-01-01",
                "authority": "CMS",
            },
            policy_key="LCD-L12345",
        )

        latest = temp_store.get_latest_version("LCD-L12345")
        meta = latest["metadata"]

        assert meta["source"] == "LCD"
        assert meta["document_type"] == "guideline"
        assert meta["effective_date"] == "2024-01-01"
        assert meta["expires_date"] == "2025-01-01"
        assert meta["authority"] == "CMS"
        # Versioning fields added automatically
        assert meta["policy_key"] == "LCD-L12345"
        assert meta["version"] == "1"
        assert meta["is_current"] is True
        assert "content_hash" in meta
        assert "created_at" in meta


class TestVersioningEdgeCases:
    """Test edge cases for versioning."""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary ChromaStore for testing."""
        temp_dir = tempfile.mkdtemp()
        store = ChromaStore(persist_dir=temp_dir, collection_name="test_policies")
        yield store
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_special_characters_in_policy_key(self, temp_store):
        """Should handle special characters in policy key."""
        result = temp_store.add_document_with_version(
            document="Policy content.",
            metadata={"source": "CMS"},
            policy_key="CMS/IOM/Ch4/Sec10",
        )

        assert result["is_duplicate"] is False
        versions = temp_store.get_document_versions("CMS/IOM/Ch4/Sec10")
        assert len(versions) == 1

    def test_whitespace_handling(self, temp_store):
        """Whitespace differences should create different hashes."""
        result1 = temp_store.add_document_with_version(
            document="Policy content.",
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
        )

        result2 = temp_store.add_document_with_version(
            document="Policy content. ",  # Trailing space
            metadata={"source": "LCD"},
            policy_key="LCD-L12345",
        )

        # Different hashes due to whitespace
        assert result2["is_duplicate"] is False
        assert result2["version"] == "2"
