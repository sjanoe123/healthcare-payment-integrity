"""Tests for the claim structuring utility."""

from __future__ import annotations

import json

import pytest

from utils.claim_structurer import (
    _parse_json_list,
    structure_claim_for_rules_engine,
)


class TestParseJsonList:
    """Tests for _parse_json_list helper."""

    def test_returns_empty_list_for_none(self):
        assert _parse_json_list(None) == []

    def test_returns_empty_list_for_empty_string(self):
        assert _parse_json_list("") == []

    def test_returns_list_unchanged(self):
        assert _parse_json_list(["a", "b", "c"]) == ["a", "b", "c"]

    def test_parses_json_string_array(self):
        assert _parse_json_list('["99213", "99214"]') == ["99213", "99214"]

    def test_parses_json_single_value(self):
        assert _parse_json_list('"99213"') == ["99213"]

    def test_returns_single_item_for_plain_string(self):
        # Plain numeric strings parse as JSON numbers
        result = _parse_json_list("99213")
        assert result == [99213] or result == ["99213"]

    def test_converts_non_string_to_list(self):
        assert _parse_json_list(12345) == ["12345"]


class TestStructureClaimForRulesEngine:
    """Tests for structure_claim_for_rules_engine."""

    def test_basic_claim_structure(self):
        claim_record = {
            "claim_id": "CLM-001",
            "patient_id": "MEM-123",
            "provider_npi": "1234567890",
            "date_of_service": "2024-01-15",
            "billed_amount": 150.00,
            "place_of_service": "11",
            "procedure_codes": '["99213", "99214"]',
            "diagnosis_codes": '["J06.9", "R05.9"]',
        }

        result = structure_claim_for_rules_engine(claim_record)

        assert result["claim_id"] == "CLM-001"
        assert result["member"]["member_id"] == "MEM-123"
        assert result["provider"]["npi"] == "1234567890"
        assert result["date_of_service"] == "2024-01-15"
        assert result["billed_amount"] == 150.00
        assert result["place_of_service"] == "11"
        assert len(result["claim_lines"]) == 2
        assert result["claim_lines"][0]["procedure_code"] == "99213"
        assert result["claim_lines"][1]["procedure_code"] == "99214"
        assert result["diagnosis_codes"] == ["J06.9", "R05.9"]

    def test_calculates_line_charge_correctly(self):
        claim_record = {
            "billed_amount": 300.00,
            "procedure_codes": '["99213", "99214", "99215"]',
        }

        result = structure_claim_for_rules_engine(claim_record)

        assert len(result["claim_lines"]) == 3
        # 300 / 3 = 100 per line
        for line in result["claim_lines"]:
            assert line["line_charge"] == 100.00

    def test_defaults_place_of_service_to_11(self):
        claim_record = {"claim_id": "CLM-001"}

        result = structure_claim_for_rules_engine(claim_record)

        assert result["place_of_service"] == "11"

    def test_extracts_member_id_from_raw_data(self):
        claim_record = {
            "raw_data": json.dumps({"member_id": "MEM-FROM-RAW"}),
        }

        result = structure_claim_for_rules_engine(claim_record)

        assert result["member"]["member_id"] == "MEM-FROM-RAW"

    def test_patient_id_takes_precedence_over_raw_data(self):
        claim_record = {
            "patient_id": "MEM-DIRECT",
            "raw_data": json.dumps({"member_id": "MEM-FROM-RAW"}),
        }

        result = structure_claim_for_rules_engine(claim_record)

        assert result["member"]["member_id"] == "MEM-DIRECT"

    def test_handles_empty_procedure_codes(self):
        claim_record = {"claim_id": "CLM-001", "procedure_codes": None}

        result = structure_claim_for_rules_engine(claim_record)

        assert result["claim_lines"] == []

    def test_handles_malformed_raw_data(self):
        claim_record = {
            "claim_id": "CLM-001",
            "raw_data": "not valid json",
        }

        # Should not raise, just use defaults
        result = structure_claim_for_rules_engine(claim_record)
        assert result["claim_id"] == "CLM-001"
        assert result["member"]["member_id"] is None

    def test_line_units_default_to_one(self):
        claim_record = {"procedure_codes": '["99213"]'}

        result = structure_claim_for_rules_engine(claim_record)

        assert result["claim_lines"][0]["units"] == 1

    def test_each_line_has_diagnosis_codes(self):
        claim_record = {
            "procedure_codes": '["99213", "99214"]',
            "diagnosis_codes": '["J06.9"]',
        }

        result = structure_claim_for_rules_engine(claim_record)

        for line in result["claim_lines"]:
            assert line["diagnosis_codes"] == ["J06.9"]
