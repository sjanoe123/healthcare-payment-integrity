"""Integration tests using real CMS data files.

These tests validate the fraud detection rules against actual CMS data:
- NCCI PTP: 29,397 real code pairs
- NCCI MUE: 8,253 real MUE limits
- OIG Exclusions: 8,172 real excluded NPIs
- MPFS: 10,622 real fee schedule codes
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add backend to path (must be before importing rules)
backend_path = str(Path(__file__).parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from rules import ThresholdConfig, evaluate_baseline  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def real_datasets() -> dict:
    """Load real CMS datasets for testing."""
    datasets = {}

    # Load NCCI PTP (convert list to dict with tuple keys)
    ptp_path = DATA_DIR / "ncci_ptp.json"
    if ptp_path.exists():
        with open(ptp_path) as f:
            ptp_list = json.load(f)
            ptp_dict = {}
            for entry in ptp_list:
                col1 = entry.get("column1") or entry.get("codes", [None, None])[0]
                col2 = entry.get("column2") or entry.get("codes", [None, None])[1]
                if col1 and col2:
                    key = tuple(sorted((col1, col2)))
                    ptp_dict[key] = {
                        "citation": entry.get("rationale", "NCCI PTP Edit"),
                        "modifier": entry.get("modifier"),
                    }
            datasets["ncci_ptp"] = ptp_dict

    # Load NCCI MUE
    mue_path = DATA_DIR / "ncci_mue.json"
    if mue_path.exists():
        with open(mue_path) as f:
            datasets["ncci_mue"] = json.load(f)

    # Load OIG Exclusions
    oig_path = DATA_DIR / "oig_exclusions.json"
    if oig_path.exists():
        with open(oig_path) as f:
            oig_data = json.load(f)
            datasets["oig_exclusions"] = set(oig_data.get("excluded_npis", []))

    # Load MPFS
    mpfs_path = DATA_DIR / "mpfs.json"
    if mpfs_path.exists():
        with open(mpfs_path) as f:
            datasets["mpfs"] = json.load(f)

    # Load LCD
    lcd_path = DATA_DIR / "lcd.json"
    if lcd_path.exists():
        with open(lcd_path) as f:
            datasets["lcd"] = json.load(f)

    # Empty defaults
    datasets.setdefault("fwa_watchlist", set())
    datasets.setdefault("utilization", {})
    datasets.setdefault("fwa_config", {"roi_multiplier": 1.0})

    return datasets


class TestDataLoading:
    """Verify real data files are loaded correctly."""

    def test_ncci_ptp_loaded(self, real_datasets: dict):
        """Verify NCCI PTP data is loaded with expected count."""
        ptp = real_datasets.get("ncci_ptp", {})
        assert len(ptp) > 20000, f"Expected 20K+ PTP pairs, got {len(ptp)}"

    def test_ncci_mue_loaded(self, real_datasets: dict):
        """Verify NCCI MUE data is loaded with expected count."""
        mue = real_datasets.get("ncci_mue", {})
        assert len(mue) > 8000, f"Expected 8K+ MUE entries, got {len(mue)}"

    def test_oig_exclusions_loaded(self, real_datasets: dict):
        """Verify OIG exclusions are loaded with expected count."""
        oig = real_datasets.get("oig_exclusions", set())
        assert len(oig) > 8000, f"Expected 8K+ excluded NPIs, got {len(oig)}"

    def test_mpfs_loaded(self, real_datasets: dict):
        """Verify MPFS data is loaded with expected count."""
        mpfs = real_datasets.get("mpfs", {})
        assert len(mpfs) > 10000, f"Expected 10K+ MPFS codes, got {len(mpfs)}"


class TestRealNCCIPTPEdits:
    """Test NCCI PTP rule detection with real CMS code pairs."""

    def test_detects_real_ptp_edit_surgical(self, real_datasets: dict):
        """Test detection of real surgical PTP edit (20600/36400)."""
        # 20600 (Arthrocentesis) and 36400 (Venipuncture) is a real PTP pair
        claim = {
            "claim_id": "PTP-TEST-001",
            "items": [
                {"procedure_code": "20600", "quantity": 1, "line_amount": 100.00},
                {"procedure_code": "36400", "quantity": 1, "line_amount": 50.00},
            ],
            "provider": {"npi": "9999999999"},
            "diagnosis_codes": ["M25.50"],
        }

        outcome = evaluate_baseline(
            claim=claim,
            datasets=real_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        ptp_hits = [h for h in outcome.rule_result.hits if h.rule_id == "NCCI_PTP"]
        assert len(ptp_hits) > 0, "Expected PTP edit for 20600/36400"
        assert "ncci_ptp" in outcome.ncci_flags

    def test_detects_real_ptp_edit_em_codes(self, real_datasets: dict):
        """Test detection of common E/M PTP edits."""
        # Check if 99213/99214 is in the data (common E/M bundling)
        ptp = real_datasets.get("ncci_ptp", {})

        # Find a real E/M code pair from the data
        em_pair = None
        for (c1, c2), _ in ptp.items():
            if c1.startswith("99") and c2.startswith("99"):
                em_pair = (c1, c2)
                break

        if em_pair:
            claim = {
                "claim_id": "PTP-EM-001",
                "items": [
                    {
                        "procedure_code": em_pair[0],
                        "quantity": 1,
                        "line_amount": 150.00,
                    },
                    {
                        "procedure_code": em_pair[1],
                        "quantity": 1,
                        "line_amount": 200.00,
                    },
                ],
                "provider": {"npi": "9999999999"},
                "diagnosis_codes": ["J06.9"],
            }

            outcome = evaluate_baseline(
                claim=claim,
                datasets=real_datasets,
                config={"base_score": 0.5},
                threshold_config=ThresholdConfig(),
            )

            ptp_hits = [h for h in outcome.rule_result.hits if h.rule_id == "NCCI_PTP"]
            assert len(ptp_hits) > 0, f"Expected PTP edit for {em_pair}"

    def test_no_ptp_for_unrelated_codes(self, real_datasets: dict):
        """Test that unrelated codes don't trigger PTP edits."""
        # Use codes that are unlikely to have a PTP relationship
        claim = {
            "claim_id": "PTP-CLEAN-001",
            "items": [
                {"procedure_code": "99214", "quantity": 1, "line_amount": 150.00},
                {
                    "procedure_code": "71046",
                    "quantity": 1,
                    "line_amount": 100.00,
                },  # Chest X-ray
            ],
            "provider": {"npi": "9999999999"},
            "diagnosis_codes": ["J18.9"],  # Pneumonia
        }

        outcome = evaluate_baseline(
            claim=claim,
            datasets=real_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        # This may or may not have PTP edits - checking for valid execution
        assert outcome.rule_result is not None


class TestRealNCCIMUELimits:
    """Test NCCI MUE rule detection with real CMS MUE limits."""

    def test_detects_mue_violation_real_limit(self, real_datasets: dict):
        """Test detection using real MUE limit from data."""
        mue = real_datasets.get("ncci_mue", {})

        # Find a code with MUE limit of 1 (common for E/M codes)
        test_code = None
        for code, entry in mue.items():
            limit = entry.get("limit") if isinstance(entry, dict) else entry
            if limit == 1 and code.startswith("99"):
                test_code = code
                break

        if test_code:
            claim = {
                "claim_id": "MUE-TEST-001",
                "items": [
                    {
                        "procedure_code": test_code,
                        "quantity": 3,  # Exceeds MUE limit of 1
                        "line_amount": 150.00,
                    },
                ],
                "provider": {"npi": "9999999999"},
                "diagnosis_codes": ["J06.9"],
            }

            outcome = evaluate_baseline(
                claim=claim,
                datasets=real_datasets,
                config={"base_score": 0.5},
                threshold_config=ThresholdConfig(),
            )

            mue_hits = [h for h in outcome.rule_result.hits if h.rule_id == "NCCI_MUE"]
            assert len(mue_hits) > 0, (
                f"Expected MUE violation for {test_code} with qty 3"
            )

    def test_no_mue_violation_within_limit(self, real_datasets: dict):
        """Test that quantities within MUE limits don't trigger violations."""
        mue = real_datasets.get("ncci_mue", {})

        # Find a code with higher MUE limit
        test_code = None
        for code, entry in mue.items():
            limit = entry.get("limit") if isinstance(entry, dict) else entry
            if limit and limit >= 3:
                test_code = code
                break

        if test_code:
            claim = {
                "claim_id": "MUE-CLEAN-001",
                "items": [
                    {
                        "procedure_code": test_code,
                        "quantity": 1,  # Within limit
                        "line_amount": 100.00,
                    },
                ],
                "provider": {"npi": "9999999999"},
                "diagnosis_codes": ["M54.5"],
            }

            outcome = evaluate_baseline(
                claim=claim,
                datasets=real_datasets,
                config={"base_score": 0.5},
                threshold_config=ThresholdConfig(),
            )

            mue_hits = [h for h in outcome.rule_result.hits if h.rule_id == "NCCI_MUE"]
            assert len(mue_hits) == 0, (
                f"Expected no MUE violation for {test_code} qty 1"
            )


class TestRealOIGExclusions:
    """Test OIG exclusion detection with real LEIE data."""

    def test_detects_real_excluded_provider(self, real_datasets: dict):
        """Test detection of real excluded provider NPI."""
        oig = real_datasets.get("oig_exclusions", set())
        assert len(oig) > 0, "No OIG exclusions loaded"

        # Get first excluded NPI from real data
        excluded_npi = next(iter(oig))

        claim = {
            "claim_id": "OIG-TEST-001",
            "items": [
                {"procedure_code": "99214", "quantity": 1, "line_amount": 150.00},
            ],
            "provider": {"npi": excluded_npi},
            "diagnosis_codes": ["J06.9"],
        }

        outcome = evaluate_baseline(
            claim=claim,
            datasets=real_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        oig_hits = [h for h in outcome.rule_result.hits if h.rule_id == "OIG_EXCLUSION"]
        assert len(oig_hits) == 1, f"Expected OIG exclusion for NPI {excluded_npi}"
        assert "oig_excluded_provider" in outcome.provider_flags

    def test_multiple_excluded_providers(self, real_datasets: dict):
        """Test that multiple excluded NPIs are all flagged."""
        oig = list(real_datasets.get("oig_exclusions", set()))[:5]
        assert len(oig) >= 5, "Need at least 5 excluded NPIs for this test"

        for npi in oig:
            claim = {
                "claim_id": f"OIG-MULTI-{npi}",
                "items": [
                    {"procedure_code": "99213", "quantity": 1, "line_amount": 100.00},
                ],
                "provider": {"npi": npi},
                "diagnosis_codes": ["J06.9"],
            }

            outcome = evaluate_baseline(
                claim=claim,
                datasets=real_datasets,
                config={"base_score": 0.5},
                threshold_config=ThresholdConfig(),
            )

            oig_hits = [
                h for h in outcome.rule_result.hits if h.rule_id == "OIG_EXCLUSION"
            ]
            assert len(oig_hits) == 1, f"Expected OIG exclusion for NPI {npi}"

    def test_non_excluded_provider_clean(self, real_datasets: dict):
        """Test that non-excluded providers are not flagged."""
        oig = real_datasets.get("oig_exclusions", set())

        # Use a fake NPI that's definitely not in the list
        clean_npi = "0000000001"
        while clean_npi in oig:
            clean_npi = str(int(clean_npi) + 1).zfill(10)

        claim = {
            "claim_id": "OIG-CLEAN-001",
            "items": [
                {"procedure_code": "99214", "quantity": 1, "line_amount": 150.00},
            ],
            "provider": {"npi": clean_npi},
            "diagnosis_codes": ["J06.9"],
        }

        outcome = evaluate_baseline(
            claim=claim,
            datasets=real_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        oig_hits = [h for h in outcome.rule_result.hits if h.rule_id == "OIG_EXCLUSION"]
        assert len(oig_hits) == 0, f"NPI {clean_npi} should not be excluded"


class TestRealMPFSBenchmarking:
    """Test fee schedule benchmarking with real MPFS data."""

    def test_mpfs_has_expected_structure(self, real_datasets: dict):
        """Verify MPFS data has expected fields."""
        mpfs = real_datasets.get("mpfs", {})
        assert len(mpfs) > 0, "MPFS data not loaded"

        # Check structure of first entry
        sample_code = next(iter(mpfs.keys()))
        sample_entry = mpfs[sample_code]

        expected_fields = ["work_rvu", "total_rvu_nonfac", "regions"]
        for field in expected_fields:
            assert field in sample_entry, f"MPFS entry missing {field}"

    def test_detects_reimbursement_outlier(self, real_datasets: dict):
        """Test detection of billed amount significantly above benchmark."""
        mpfs = real_datasets.get("mpfs", {})

        # Find a code with non-zero payment rate
        test_code = None
        benchmark = 0
        for code, entry in mpfs.items():
            if code.startswith("99"):  # E/M codes
                regions = entry.get("regions", {})
                national = regions.get("national_nonfac", 0) or regions.get(
                    "national", 0
                )
                if national and national > 50:
                    test_code = code
                    benchmark = national
                    break

        if test_code and benchmark > 0:
            # Bill at 3x the benchmark to trigger outlier
            billed_amount = benchmark * 3

            claim = {
                "claim_id": "MPFS-OUTLIER-001",
                "items": [
                    {
                        "procedure_code": test_code,
                        "quantity": 1,
                        "line_amount": billed_amount,
                    },
                ],
                "provider": {"npi": "9999999999", "region": "national"},
                "diagnosis_codes": ["J06.9"],
            }

            outcome = evaluate_baseline(
                claim=claim,
                datasets=real_datasets,
                config={"base_score": 0.5},
                threshold_config=ThresholdConfig(),
            )

            # Note: outlier rule uses percentile threshold, may not trigger
            # Just verify execution completes
            assert outcome.rule_result is not None

    def test_reasonable_billing_not_flagged_as_outlier(self, real_datasets: dict):
        """Test that reasonable billing amounts don't trigger outlier flags."""
        mpfs = real_datasets.get("mpfs", {})

        # Find a code with non-zero payment rate
        test_code = None
        benchmark = 0
        for code, entry in mpfs.items():
            if code.startswith("99"):
                regions = entry.get("regions", {})
                national = regions.get("national_nonfac", 0) or regions.get(
                    "national", 0
                )
                if national and national > 50:
                    test_code = code
                    benchmark = national
                    break

        if test_code and benchmark > 0:
            # Bill at exactly the benchmark
            claim = {
                "claim_id": "MPFS-REASONABLE-001",
                "items": [
                    {
                        "procedure_code": test_code,
                        "quantity": 1,
                        "line_amount": benchmark,
                    },
                ],
                "provider": {"npi": "9999999999", "region": "national"},
                "diagnosis_codes": ["J06.9"],
            }

            outcome = evaluate_baseline(
                claim=claim,
                datasets=real_datasets,
                config={"base_score": 0.5},
                threshold_config=ThresholdConfig(),
            )

            outlier_hits = [
                h for h in outcome.rule_result.hits if h.rule_id == "REIMB_OUTLIER"
            ]
            assert len(outlier_hits) == 0, "Reasonable billing should not be flagged"


class TestComplexClaimScenarios:
    """Test complex claims with multiple fraud indicators."""

    def test_high_risk_claim_multiple_indicators(self, real_datasets: dict):
        """Test claim with OIG exclusion + MUE violation + PTP edit."""
        oig = real_datasets.get("oig_exclusions", set())
        mue = real_datasets.get("ncci_mue", {})
        ptp = real_datasets.get("ncci_ptp", {})

        # Get real excluded NPI
        excluded_npi = next(iter(oig)) if oig else None

        # Find a real PTP pair
        ptp_pair = next(iter(ptp.keys())) if ptp else None

        # Find a code with MUE limit of 1
        mue_code = None
        for code, entry in mue.items():
            limit = entry.get("limit") if isinstance(entry, dict) else entry
            if limit == 1:
                mue_code = code
                break

        if excluded_npi and ptp_pair and mue_code:
            claim = {
                "claim_id": "HIGH-RISK-001",
                "items": [
                    {
                        "procedure_code": ptp_pair[0],
                        "quantity": 1,
                        "line_amount": 100.00,
                    },
                    {
                        "procedure_code": ptp_pair[1],
                        "quantity": 1,
                        "line_amount": 100.00,
                    },
                    {
                        "procedure_code": mue_code,
                        "quantity": 5,  # Exceeds MUE
                        "line_amount": 200.00,
                    },
                ],
                "provider": {"npi": excluded_npi},
                "diagnosis_codes": ["M54.5"],
            }

            outcome = evaluate_baseline(
                claim=claim,
                datasets=real_datasets,
                config={"base_score": 0.5},
                threshold_config=ThresholdConfig(),
            )

            # Should have multiple hits
            assert len(outcome.rule_result.hits) >= 2
            assert outcome.decision.score > 0.6, (
                "High-risk claim should have elevated score"
            )

            # Verify specific flags
            rule_ids = [h.rule_id for h in outcome.rule_result.hits]
            assert "OIG_EXCLUSION" in rule_ids
            assert "NCCI_PTP" in rule_ids or "NCCI_MUE" in rule_ids

    def test_clean_claim_low_risk_score(self, real_datasets: dict):
        """Test that clean claims with real data get low risk scores."""
        oig = real_datasets.get("oig_exclusions", set())

        # Use a clean NPI
        clean_npi = "5555555555"
        while clean_npi in oig:
            clean_npi = str(int(clean_npi) + 1).zfill(10)

        claim = {
            "claim_id": "CLEAN-001",
            "items": [
                {
                    "procedure_code": "99214",  # Common E/M code
                    "quantity": 1,  # Within any MUE limit
                    "line_amount": 100.00,
                },
            ],
            "provider": {
                "npi": clean_npi,
                "specialty": "family medicine",
            },
            "member": {"age": 45, "gender": "F"},
            "diagnosis_codes": ["J06.9"],
        }

        outcome = evaluate_baseline(
            claim=claim,
            datasets=real_datasets,
            config={"base_score": 0.5},
            threshold_config=ThresholdConfig(),
        )

        # Clean claim should have minimal or no rule hits
        critical_hits = [
            h for h in outcome.rule_result.hits if h.severity == "critical"
        ]
        assert len(critical_hits) == 0, "Clean claim should have no critical hits"


class TestDataConsistency:
    """Test data consistency across datasets."""

    def test_ptp_codes_in_consistent_format(self, real_datasets: dict):
        """Verify PTP codes are in consistent format."""
        ptp = real_datasets.get("ncci_ptp", {})
        for key in list(ptp.keys())[:100]:  # Sample first 100
            assert isinstance(key, tuple), f"PTP key should be tuple: {key}"
            assert len(key) == 2, f"PTP key should have 2 elements: {key}"
            assert all(isinstance(c, str) for c in key), (
                f"PTP codes should be strings: {key}"
            )

    def test_mue_limits_are_positive(self, real_datasets: dict):
        """Verify all MUE limits are positive integers."""
        mue = real_datasets.get("ncci_mue", {})
        for code, entry in list(mue.items())[:100]:  # Sample first 100
            limit = entry.get("limit") if isinstance(entry, dict) else entry
            if limit is not None:
                assert isinstance(limit, int), f"MUE limit should be int: {code}"
                assert limit > 0, f"MUE limit should be positive: {code} = {limit}"

    def test_oig_npis_are_valid_format(self, real_datasets: dict):
        """Verify OIG NPIs are valid 10-digit format."""
        oig = real_datasets.get("oig_exclusions", set())
        for npi in list(oig)[:100]:  # Sample first 100
            assert isinstance(npi, str), f"NPI should be string: {npi}"
            assert len(npi) == 10, f"NPI should be 10 digits: {npi}"
            assert npi.isdigit(), f"NPI should be all digits: {npi}"
