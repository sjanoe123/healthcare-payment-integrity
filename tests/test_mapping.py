"""Tests for the semantic schema mapping module."""

from unittest.mock import MagicMock, patch

import pytest

from mapping import FieldMapper, MappingResult, normalize_claim, normalize_claim_with_review
from mapping.omop_schema import (
    ALIAS_LOOKUP,
    OMOP_CLAIMS_SCHEMA,
    REQUIRED_FIELDS,
    get_all_aliases,
)
from mapping.templates import (
    CSV_GENERIC_MAPPING,
    EDI_837I_MAPPING,
    EDI_837P_MAPPING,
    get_template,
)


class TestOMOPSchema:
    """Tests for OMOP CDM schema definition."""

    def test_schema_has_required_fields(self):
        """Verify schema defines required fields."""
        assert "visit_occurrence_id" in OMOP_CLAIMS_SCHEMA
        assert "person_id" in OMOP_CLAIMS_SCHEMA
        assert "npi" in OMOP_CLAIMS_SCHEMA
        assert "procedure_source_value" in OMOP_CLAIMS_SCHEMA

    def test_aliases_defined_for_common_variations(self):
        """Verify aliases exist for common field name variations."""
        person_field = OMOP_CLAIMS_SCHEMA["person_id"]
        assert "member_id" in person_field.aliases
        assert "patient_id" in person_field.aliases
        assert "subscriber_id" in person_field.aliases

        date_field = OMOP_CLAIMS_SCHEMA["visit_start_date"]
        assert "service_date" in date_field.aliases
        assert "dos" in date_field.aliases
        assert "date_of_service" in date_field.aliases

    def test_alias_lookup_is_case_insensitive(self):
        """Verify alias lookup works case-insensitively."""
        assert "patient_id" in ALIAS_LOOKUP
        assert ALIAS_LOOKUP["patient_id"] == "person_id"
        assert ALIAS_LOOKUP["memberid"] == "person_id"

    def test_required_fields_identified(self):
        """Verify required fields are properly identified."""
        assert "visit_occurrence_id" in REQUIRED_FIELDS
        assert "person_id" in REQUIRED_FIELDS
        assert "npi" in REQUIRED_FIELDS


class TestFieldMapper:
    """Tests for the FieldMapper class."""

    def test_transform_with_canonical_field_names(self):
        """Test transform when input already uses canonical names."""
        mapper = FieldMapper()
        raw = {
            "visit_occurrence_id": "CLM001",
            "person_id": "P123",
            "visit_start_date": "2024-01-15",
            "npi": "1234567890",
        }
        result = mapper.transform(raw)

        assert result["visit_occurrence_id"] == "CLM001"
        assert result.get("person_id") == "P123" or result["member"]["person_id"] == "P123"

    def test_transform_with_aliases(self):
        """Test transform with common aliases."""
        mapper = FieldMapper()
        raw = {
            "claim_id": "CLM002",
            "patient_id": "P456",
            "dos": "2024-02-20",
            "rendering_npi": "9876543210",
        }
        result = mapper.transform(raw)

        assert result["visit_occurrence_id"] == "CLM002"
        assert result.get("person_id") == "P456" or result["member"]["person_id"] == "P456"
        assert result["visit_start_date"] == "2024-02-20"

    def test_transform_with_nested_structures(self):
        """Test transform preserves nested member/provider data."""
        mapper = FieldMapper()
        raw = {
            "claim_id": "CLM003",
            "member": {"member_id": "M789", "age": 45, "gender": "F"},
            "provider": {"npi": "1111111111", "specialty": "Cardiology"},
            "items": [{"procedure_code": "99213", "quantity": 1}],
        }
        result = mapper.transform(raw)

        assert result["member"]["person_id"] == "M789"
        assert result["member"]["age"] == 45
        assert result["provider"]["npi"] == "1111111111"
        assert result["provider"]["specialty_source_value"] == "Cardiology"

    def test_transform_with_custom_mapping(self):
        """Test transform with custom mapping overrides."""
        custom = {"CustomMemberField": "person_id"}
        mapper = FieldMapper(custom_mapping=custom)
        raw = {"CustomMemberField": "CM001", "claim_id": "CLM004"}
        result = mapper.transform(raw)

        # Custom mapping should take precedence
        assert result.get("person_id") == "CM001" or result["member"]["person_id"] == "CM001"

    def test_transform_items_normalization(self):
        """Test that line items are normalized correctly."""
        mapper = FieldMapper()
        raw = {
            "claim_id": "CLM005",
            "items": [
                {"cpt_code": "99213", "units": 1, "charge_amount": 150.00},
                {"hcpcs_code": "J3301", "quantity": 2, "line_amount": 25.00},
            ],
        }
        result = mapper.transform(raw)

        assert len(result["items"]) == 2
        assert result["items"][0]["procedure_source_value"] == "99213"
        assert result["items"][0]["quantity"] == 1
        assert result["items"][1]["procedure_source_value"] == "J3301"

    def test_strict_mode_raises_on_missing_required(self):
        """Test strict mode raises error for missing required fields."""
        mapper = FieldMapper(strict_mode=True)
        raw = {"some_field": "value"}  # Missing required fields

        with pytest.raises(ValueError, match="Missing required fields"):
            mapper.transform(raw)


class TestNormalizeClaim:
    """Tests for the normalize_claim convenience function."""

    def test_normalize_claim_basic(self):
        """Test basic claim normalization."""
        raw = {
            "patient_id": "P001",
            "service_date": "2024-03-15",
            "provider_npi": "5555555555",
        }
        result = normalize_claim(raw)

        assert result.get("person_id") == "P001" or result["member"]["person_id"] == "P001"
        assert result["visit_start_date"] == "2024-03-15"

    def test_normalize_claim_with_template(self):
        """Test normalization with custom template mapping."""
        raw = {"subscriber_identifier": "S001"}
        result = normalize_claim(raw, custom_mapping=EDI_837P_MAPPING)

        # The template maps subscriber_identifier -> person_id
        assert result.get("person_id") == "S001" or result["member"]["person_id"] == "S001"


class TestMappingTemplates:
    """Tests for pre-built mapping templates."""

    def test_edi_837p_template_exists(self):
        """Verify EDI 837P template is available."""
        template = get_template("edi_837p")
        assert template is not None
        assert "subscriber_identifier" in template
        assert "rendering_provider_npi" in template

    def test_edi_837i_template_exists(self):
        """Verify EDI 837I template is available."""
        template = get_template("edi_837i")
        assert template is not None
        assert "patient_control_number" in template
        assert "attending_provider_npi" in template

    def test_csv_template_exists(self):
        """Verify CSV template is available."""
        template = get_template("csv")
        assert template is not None
        assert "MemberID" in template
        assert "ServiceDate" in template

    def test_invalid_template_raises_error(self):
        """Test that invalid template name raises error."""
        with pytest.raises(ValueError, match="Unknown template"):
            get_template("invalid_template_name")

    def test_template_case_insensitive(self):
        """Test that template names are case-insensitive."""
        assert get_template("EDI_837P") == get_template("edi_837p")
        assert get_template("CSV") == get_template("csv")


class TestMappingResult:
    """Tests for the MappingResult class."""

    def test_add_mapping(self):
        """Test adding a successful mapping."""
        result = MappingResult()
        result.add_mapping("person_id", "P001", "patient_id", confidence=0.95)

        assert result.mapped_fields["person_id"] == "P001"
        assert result.mapping_sources["person_id"] == "patient_id"
        assert result.confidence_scores["person_id"] == 0.95

    def test_add_unmapped(self):
        """Test tracking unmapped fields."""
        result = MappingResult()
        result.add_unmapped("unknown_field")
        result.add_unmapped("another_unknown")

        assert "unknown_field" in result.unmapped_fields
        assert "another_unknown" in result.unmapped_fields

    def test_no_duplicate_unmapped(self):
        """Test that unmapped fields are not duplicated."""
        result = MappingResult()
        result.add_unmapped("same_field")
        result.add_unmapped("same_field")

        assert result.unmapped_fields.count("same_field") == 1


class TestRealWorldScenarios:
    """Integration tests with realistic claim data."""

    def test_edi_837p_claim(self):
        """Test normalization of EDI 837P professional claim."""
        edi_claim = {
            "clm01": "CLM2024001",
            "clm02": 525.00,
            "nm109": "SUB123456",
            "dmg02": "1980-05-15",
            "dmg03": "M",
            "dtp03_472": "2024-01-15",
            "nm109_82": "1234567890",
            "prv03": "207Q00000X",  # Family Medicine taxonomy
            "items": [
                {
                    "sv101_1": "99214",
                    "sv101_2": "25",
                    "sv102": 175.00,
                    "sv104": 1,
                },
                {
                    "sv101_1": "36415",
                    "sv102": 15.00,
                    "sv104": 1,
                },
            ],
        }

        result = normalize_claim(edi_claim, custom_mapping=EDI_837P_MAPPING)

        assert result["visit_occurrence_id"] == "CLM2024001"
        assert result["total_charge"] == 525.00
        assert result["visit_start_date"] == "2024-01-15"

    def test_csv_export_claim(self):
        """Test normalization of typical CSV export format."""
        csv_claim = {
            "ClaimID": "CSV-2024-001",
            "MemberID": "MEM789",
            "PatientDOB": "1975-08-22",
            "ServiceDate": "2024-02-28",
            "ProviderNPI": "9876543210",
            "Specialty": "Internal Medicine",
            "BilledAmount": 350.00,
            "items": [
                {"CPTCode": "99213", "Units": 1, "ChargeAmount": 125.00},
                {"CPTCode": "81001", "Units": 1, "ChargeAmount": 35.00},
            ],
        }

        result = normalize_claim(csv_claim, custom_mapping=CSV_GENERIC_MAPPING)

        assert result["visit_occurrence_id"] == "CSV-2024-001"
        assert result["total_charge"] == 350.00
        assert result.get("person_id") == "MEM789" or result["member"]["person_id"] == "MEM789"


class TestEmbeddingMatcher:
    """Tests for the EmbeddingMatcher class (with mocking)."""

    def test_embedding_matcher_import(self):
        """Test that EmbeddingMatcher can be imported."""
        from mapping.embeddings import EmbeddingMatcher, EMBEDDING_MODELS

        assert EmbeddingMatcher is not None
        assert "pubmedbert" in EMBEDDING_MODELS
        assert "minilm" in EMBEDDING_MODELS

    def test_embedding_matcher_initialization(self):
        """Test EmbeddingMatcher initializes without loading model."""
        from mapping.embeddings import EmbeddingMatcher

        matcher = EmbeddingMatcher()
        # Model should not be loaded until first use
        assert matcher._model is None
        assert matcher._initialized is False

    def test_embedding_matcher_normalize_field_name(self):
        """Test field name normalization."""
        from mapping.embeddings import EmbeddingMatcher

        # Static method should work without initialization
        assert EmbeddingMatcher._normalize_field_name("PatientID") == "Patient ID"
        assert EmbeddingMatcher._normalize_field_name("patient_id") == "patient id"
        assert EmbeddingMatcher._normalize_field_name("memberFirstName") == "member First Name"
        # Strips common prefixes (then applies camelCase splitting)
        assert EmbeddingMatcher._normalize_field_name("fld MemberID") == "Member ID"

    @patch("mapping.embeddings.EmbeddingMatcher._ensure_initialized")
    def test_find_candidates_structure(self, mock_init):
        """Test find_candidates returns correct structure with mock."""
        from mapping.embeddings import EmbeddingMatcher
        import numpy as np

        matcher = EmbeddingMatcher()
        matcher._initialized = True
        matcher._canonical_fields = ["person_id", "npi", "visit_start_date"]
        matcher._canonical_embeddings = np.random.rand(3, 384).astype(np.float32)

        # Mock the encode method
        matcher._model = MagicMock()
        matcher._model.encode.return_value = np.random.rand(384).astype(np.float32)

        # Mock cosine similarity to return predictable values
        with patch("mapping.embeddings.EmbeddingMatcher._cosine_similarity") as mock_cos:
            mock_cos.return_value = np.array([[0.9, 0.5, 0.3]])
            candidates = matcher.find_candidates("PatientID", top_k=3, min_similarity=0.1)

        assert len(candidates) == 3
        assert candidates[0][0] == "person_id"  # Highest similarity
        assert candidates[0][1] == 0.9

    @patch("mapping.embeddings.EmbeddingMatcher._ensure_initialized")
    def test_find_best_match(self, mock_init):
        """Test find_best_match returns single best match."""
        from mapping.embeddings import EmbeddingMatcher
        import numpy as np

        matcher = EmbeddingMatcher()
        matcher._initialized = True
        matcher._canonical_fields = ["person_id", "npi"]
        matcher._canonical_embeddings = np.random.rand(2, 384).astype(np.float32)
        matcher._model = MagicMock()
        matcher._model.encode.return_value = np.random.rand(384).astype(np.float32)

        with patch("mapping.embeddings.EmbeddingMatcher._cosine_similarity") as mock_cos:
            mock_cos.return_value = np.array([[0.85, 0.5]])
            result = matcher.find_best_match("MemberNumber", min_similarity=0.7)

        assert result is not None
        assert result[0] == "person_id"
        assert result[1] == 0.85

    @patch("mapping.embeddings.EmbeddingMatcher._ensure_initialized")
    def test_find_best_match_below_threshold(self, mock_init):
        """Test find_best_match returns None when below threshold."""
        from mapping.embeddings import EmbeddingMatcher
        import numpy as np

        matcher = EmbeddingMatcher()
        matcher._initialized = True
        matcher._canonical_fields = ["person_id"]
        matcher._canonical_embeddings = np.random.rand(1, 384).astype(np.float32)
        matcher._model = MagicMock()
        matcher._model.encode.return_value = np.random.rand(384).astype(np.float32)

        with patch("mapping.embeddings.EmbeddingMatcher._cosine_similarity") as mock_cos:
            mock_cos.return_value = np.array([[0.5]])  # Below 0.7 threshold
            result = matcher.find_best_match("RandomField", min_similarity=0.7)

        assert result is None


class TestSemanticMatching:
    """Tests for semantic matching integration in FieldMapper."""

    def test_mapper_with_semantic_disabled(self):
        """Test that mapper works without semantic matching."""
        mapper = FieldMapper(use_semantic_matching=False)
        raw = {"UnknownField": "value123"}
        result = mapper.transform(raw)

        # UnknownField should not be mapped
        assert "UnknownField" not in result

    @patch("mapping.mapper.FieldMapper._resolve_semantic")
    def test_mapper_calls_semantic_for_unknown_fields(self, mock_semantic):
        """Test that mapper calls semantic matching for unknown fields."""
        mock_semantic.return_value = "person_id"

        mapper = FieldMapper(use_semantic_matching=True, semantic_threshold=0.7)
        raw = {"PatientMRN": "P001", "claim_id": "CLM001"}
        result = mapper.transform(raw)

        # PatientMRN should trigger semantic matching (not a known alias)
        # claim_id is a known alias, should not trigger semantic
        mock_semantic.assert_called()

    def test_get_semantic_matches_empty_initially(self):
        """Test that semantic matches dict is empty initially."""
        mapper = FieldMapper(use_semantic_matching=True)
        assert mapper.get_semantic_matches() == {}

    def test_clear_semantic_matches(self):
        """Test clearing semantic matches."""
        mapper = FieldMapper(use_semantic_matching=True)
        mapper._semantic_matches["test"] = ("field", 0.9)
        mapper.clear_semantic_matches()
        assert mapper.get_semantic_matches() == {}

    def test_mapper_semantic_threshold_parameter(self):
        """Test that semantic threshold is configurable."""
        mapper = FieldMapper(use_semantic_matching=True, semantic_threshold=0.85)
        assert mapper.semantic_threshold == 0.85


class TestNormalizeClaimWithReview:
    """Tests for normalize_claim_with_review function."""

    def test_normalize_with_review_returns_tuple(self):
        """Test that normalize_claim_with_review returns correct structure."""
        raw = {"claim_id": "CLM001", "member_id": "M001"}
        result, semantic_matches = normalize_claim_with_review(raw)

        assert isinstance(result, dict)
        assert isinstance(semantic_matches, dict)
        assert result["visit_occurrence_id"] == "CLM001"

    def test_normalize_with_review_custom_threshold(self):
        """Test custom semantic threshold in normalize_claim_with_review."""
        raw = {"claim_id": "CLM001"}
        result, _ = normalize_claim_with_review(raw, semantic_threshold=0.9)

        # Should still normalize known fields
        assert result["visit_occurrence_id"] == "CLM001"

    def test_normalize_with_review_custom_mapping(self):
        """Test custom mapping in normalize_claim_with_review."""
        custom = {"MyCustomField": "person_id"}
        raw = {"MyCustomField": "P123", "claim_id": "CLM001"}
        result, _ = normalize_claim_with_review(raw, custom_mapping=custom)

        assert result.get("person_id") == "P123" or result["member"]["person_id"] == "P123"


class TestReranker:
    """Tests for the MappingReranker class."""

    def test_reranker_import(self):
        """Test that reranker components can be imported."""
        from mapping.reranker import (
            MappingReranker,
            RerankerResult,
            HIGH_CONFIDENCE_THRESHOLD,
            LOW_CONFIDENCE_THRESHOLD,
        )

        assert MappingReranker is not None
        assert RerankerResult is not None
        assert HIGH_CONFIDENCE_THRESHOLD == 85
        assert LOW_CONFIDENCE_THRESHOLD == 50

    def test_reranker_result_dataclass(self):
        """Test RerankerResult dataclass methods."""
        from mapping.reranker import RerankerResult

        result = RerankerResult(
            target_field="person_id",
            confidence=90,
            reasoning="Good semantic match",
            source_field="PatientMRN",
            embedding_score=0.85,
            model="claude-haiku-4-5-20250514",
            tokens_used=150,
        )

        assert result.target_field == "person_id"
        assert result.confidence == 90
        assert not result.needs_review()  # 90 >= 85
        assert not result.is_low_confidence()  # 90 >= 50

        result_dict = result.to_dict()
        assert result_dict["target_field"] == "person_id"
        assert result_dict["confidence"] == 90
        assert result_dict["needs_review"] is False

    def test_reranker_result_needs_review(self):
        """Test RerankerResult review thresholds."""
        from mapping.reranker import RerankerResult

        # Below high confidence threshold
        result = RerankerResult(
            target_field="npi",
            confidence=75,
            reasoning="Moderate match",
            source_field="ProviderNum",
            embedding_score=0.72,
            model="test",
            tokens_used=100,
        )

        assert result.needs_review()  # 75 < 85
        assert not result.is_low_confidence()  # 75 >= 50

    def test_reranker_result_low_confidence(self):
        """Test RerankerResult low confidence detection."""
        from mapping.reranker import RerankerResult

        result = RerankerResult(
            target_field="visit_occurrence_id",
            confidence=40,
            reasoning="Weak match",
            source_field="SomeRandomField",
            embedding_score=0.45,
            model="test",
            tokens_used=100,
        )

        assert result.needs_review()  # 40 < 85
        assert result.is_low_confidence()  # 40 < 50

    def test_reranker_initialization(self):
        """Test MappingReranker initialization."""
        from mapping.reranker import MappingReranker, RERANKER_MODEL

        reranker = MappingReranker()
        assert reranker.model == RERANKER_MODEL
        assert reranker.high_confidence_threshold == 85
        assert reranker.low_confidence_threshold == 50
        assert reranker._client is None  # Lazy-loaded

    def test_reranker_custom_thresholds(self):
        """Test MappingReranker with custom thresholds."""
        from mapping.reranker import MappingReranker

        reranker = MappingReranker(
            high_confidence_threshold=90,
            low_confidence_threshold=60,
        )
        assert reranker.high_confidence_threshold == 90
        assert reranker.low_confidence_threshold == 60

    def test_reranker_empty_candidates(self):
        """Test reranker with empty candidates returns None."""
        from mapping.reranker import MappingReranker

        reranker = MappingReranker()
        result = reranker.rerank("SomeField", [])
        assert result is None

    @patch("mapping.reranker.MappingReranker._get_client")
    def test_reranker_with_mock_client(self, mock_get_client):
        """Test reranker with mocked Claude client."""
        from mapping.reranker import MappingReranker

        # Create mock client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='{"target_field": "person_id", "confidence": 92, "reasoning": "Patient identifier match"}'
            )
        ]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        reranker = MappingReranker()
        result = reranker.rerank(
            source_field="PatientMRN",
            candidates=[("person_id", 0.85), ("visit_occurrence_id", 0.70)],
            sample_values=["MRN-123", "MRN-456"],
        )

        assert result is not None
        assert result.target_field == "person_id"
        assert result.confidence == 92
        assert result.source_field == "PatientMRN"
        assert result.embedding_score == 0.85
        assert not result.needs_review()

    @patch("mapping.reranker.MappingReranker._get_client")
    def test_reranker_batch(self, mock_get_client):
        """Test batch reranking."""
        from mapping.reranker import MappingReranker

        # Create mock client
        mock_client = MagicMock()

        def create_response(field, conf):
            resp = MagicMock()
            resp.content = [
                MagicMock(
                    text=f'{{"target_field": "{field}", "confidence": {conf}, "reasoning": "test"}}'
                )
            ]
            resp.usage.input_tokens = 50
            resp.usage.output_tokens = 25
            return resp

        mock_client.messages.create.side_effect = [
            create_response("person_id", 90),
            create_response("npi", 85),
        ]
        mock_get_client.return_value = mock_client

        reranker = MappingReranker()
        results = reranker.batch_rerank(
            [
                {"source_field": "MemberID", "candidates": [("person_id", 0.9)]},
                {"source_field": "ProviderNPI", "candidates": [("npi", 0.88)]},
            ]
        )

        assert len(results) == 2
        assert results[0].target_field == "person_id"
        assert results[1].target_field == "npi"


class TestMappingPersistence:
    """Tests for the MappingStore persistence layer."""

    def test_persistence_import(self):
        """Test that persistence components can be imported."""
        from mapping.persistence import (
            MappingStore,
            SchemaMapping,
            FieldMappingEntry,
            MappingStatus,
            MappingAction,
        )

        assert MappingStore is not None
        assert SchemaMapping is not None
        assert FieldMappingEntry is not None
        assert MappingStatus.PENDING.value == "pending"
        assert MappingAction.CREATED.value == "created"

    def test_field_mapping_entry_dataclass(self):
        """Test FieldMappingEntry dataclass."""
        from mapping.persistence import FieldMappingEntry

        entry = FieldMappingEntry(
            source_field="PatientMRN",
            target_field="person_id",
            confidence=0.92,
            method="llm_rerank",
            reasoning="Patient identifier match",
        )

        assert entry.source_field == "PatientMRN"
        assert entry.target_field == "person_id"
        assert entry.confidence == 0.92
        assert entry.method == "llm_rerank"

    def test_schema_mapping_to_dict(self):
        """Test SchemaMapping.to_dict() method."""
        from mapping.persistence import SchemaMapping, FieldMappingEntry, MappingStatus

        mapping = SchemaMapping(
            id="test-123",
            source_schema_id="payer_a",
            source_schema_version=1,
            target_schema="omop_cdm_5.4",
            field_mappings=[
                FieldMappingEntry(
                    source_field="MemberID",
                    target_field="person_id",
                    confidence=0.95,
                    method="semantic",
                )
            ],
            status=MappingStatus.PENDING,
            created_at="2024-01-15T10:30:00Z",
            created_by="user@example.com",
        )

        result = mapping.to_dict()
        assert result["id"] == "test-123"
        assert result["source_schema_id"] == "payer_a"
        assert result["status"] == "pending"
        assert len(result["field_mappings"]) == 1
        assert result["field_mappings"][0]["source_field"] == "MemberID"

    def test_mapping_store_init(self, tmp_path):
        """Test MappingStore initialization creates tables."""
        from mapping.persistence import MappingStore
        import sqlite3

        db_path = str(tmp_path / "test.db")
        store = MappingStore(db_path)

        # Verify tables were created
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}

        assert "schema_mappings" in tables
        assert "mapping_audit_log" in tables

    def test_mapping_store_save_and_get(self, tmp_path):
        """Test saving and retrieving a mapping."""
        from mapping.persistence import MappingStore, MappingStatus

        db_path = str(tmp_path / "test.db")
        store = MappingStore(db_path)

        # Save a mapping
        mapping = store.save_mapping(
            source_schema_id="test_schema",
            field_mappings=[
                {
                    "source_field": "PatientID",
                    "target_field": "person_id",
                    "confidence": 0.9,
                    "method": "semantic",
                }
            ],
            created_by="tester",
        )

        assert mapping.source_schema_id == "test_schema"
        assert mapping.source_schema_version == 1
        assert mapping.status == MappingStatus.PENDING
        assert len(mapping.field_mappings) == 1

        # Retrieve it
        retrieved = store.get_mapping("test_schema")
        assert retrieved is not None
        assert retrieved.id == mapping.id

    def test_mapping_store_versioning(self, tmp_path):
        """Test that saving creates new versions."""
        from mapping.persistence import MappingStore

        db_path = str(tmp_path / "test.db")
        store = MappingStore(db_path)

        # Save first version
        v1 = store.save_mapping(
            source_schema_id="versioned_schema",
            field_mappings=[{"source_field": "A", "target_field": "a"}],
        )
        assert v1.source_schema_version == 1

        # Save second version
        v2 = store.save_mapping(
            source_schema_id="versioned_schema",
            field_mappings=[{"source_field": "B", "target_field": "b"}],
        )
        assert v2.source_schema_version == 2

        # Get specific version
        retrieved_v1 = store.get_mapping("versioned_schema", version=1)
        assert retrieved_v1.field_mappings[0].source_field == "A"

        # Get latest (default)
        retrieved_latest = store.get_mapping("versioned_schema")
        assert retrieved_latest.source_schema_version == 2

    def test_mapping_store_approve(self, tmp_path):
        """Test approving a mapping."""
        from mapping.persistence import MappingStore, MappingStatus

        db_path = str(tmp_path / "test.db")
        store = MappingStore(db_path)

        mapping = store.save_mapping(
            source_schema_id="approval_test",
            field_mappings=[{"source_field": "X", "target_field": "x"}],
        )

        approved = store.approve_mapping(mapping.id, approved_by="approver@test.com")

        assert approved is not None
        assert approved.status == MappingStatus.APPROVED
        assert approved.approved_by == "approver@test.com"
        assert approved.approved_at is not None

    def test_mapping_store_reject(self, tmp_path):
        """Test rejecting a mapping."""
        from mapping.persistence import MappingStore, MappingStatus

        db_path = str(tmp_path / "test.db")
        store = MappingStore(db_path)

        mapping = store.save_mapping(
            source_schema_id="rejection_test",
            field_mappings=[{"source_field": "Y", "target_field": "y"}],
        )

        rejected = store.reject_mapping(
            mapping.id,
            rejected_by="reviewer@test.com",
            reason="Low confidence fields",
        )

        assert rejected is not None
        assert rejected.status == MappingStatus.REJECTED

    def test_mapping_store_audit_log(self, tmp_path):
        """Test audit log entries are created."""
        from mapping.persistence import MappingStore, MappingAction

        db_path = str(tmp_path / "test.db")
        store = MappingStore(db_path)

        mapping = store.save_mapping(
            source_schema_id="audit_test",
            field_mappings=[{"source_field": "Z", "target_field": "z"}],
            created_by="creator@test.com",
        )

        store.approve_mapping(mapping.id, approved_by="approver@test.com")

        logs = store.get_audit_log(mapping.id)

        assert len(logs) == 2
        # Most recent first
        assert logs[0].action == MappingAction.APPROVED
        assert logs[1].action == MappingAction.CREATED

    def test_mapping_store_list_by_status(self, tmp_path):
        """Test listing mappings by status."""
        from mapping.persistence import MappingStore, MappingStatus

        db_path = str(tmp_path / "test.db")
        store = MappingStore(db_path)

        # Create some mappings
        m1 = store.save_mapping("schema1", [{"source_field": "a", "target_field": "A"}])
        m2 = store.save_mapping("schema2", [{"source_field": "b", "target_field": "B"}])
        store.approve_mapping(m2.id, approved_by="test")

        # List pending
        pending = store.list_mappings(status=MappingStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].source_schema_id == "schema1"

        # List approved
        approved = store.list_mappings(status=MappingStatus.APPROVED)
        assert len(approved) == 1
        assert approved[0].source_schema_id == "schema2"
