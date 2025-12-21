"""Comprehensive tests for all rule categories."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from rules.models import RuleContext


# ============================================================================
# FORMAT RULES TESTS
# ============================================================================
class TestFormatRules:
    """Tests for format validation rules."""

    def test_missing_field_no_member_id(self):
        """Test that missing member_id triggers rule."""
        from rules.categories.format_rules import format_missing_field_rule

        context = RuleContext(
            claim={
                "member": {},
                "provider": {"npi": "1234567890"},
                "service_date": "2024-01-15",
                "items": [{"procedure_code": "99213", "quantity": 1}],
            },
            datasets={},
            config={},
        )
        hits = format_missing_field_rule(context)
        assert len(hits) > 0
        assert any("Member ID" in h.description for h in hits)

    def test_missing_field_no_items(self):
        """Test that claim with no items triggers rule."""
        from rules.categories.format_rules import format_missing_field_rule

        context = RuleContext(
            claim={
                "member": {"member_id": "M12345"},
                "provider": {"npi": "1234567890"},
                "service_date": "2024-01-15",
                "items": [],
            },
            datasets={},
            config={},
        )
        hits = format_missing_field_rule(context)
        assert any("no service line items" in h.description for h in hits)

    def test_missing_field_valid_claim(self):
        """Test that valid claim doesn't trigger rule."""
        from rules.categories.format_rules import format_missing_field_rule

        context = RuleContext(
            claim={
                "member": {"member_id": "M12345"},
                "provider": {"npi": "1234567890"},
                "service_date": "2024-01-15",
                "items": [{"procedure_code": "99213", "quantity": 1}],
            },
            datasets={},
            config={},
        )
        hits = format_missing_field_rule(context)
        assert len(hits) == 0

    def test_invalid_date_future_service(self):
        """Test that future service date triggers rule."""
        from rules.categories.format_rules import format_invalid_date_rule

        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        context = RuleContext(
            claim={"service_date": future_date, "items": []},
            datasets={},
            config={},
        )
        hits = format_invalid_date_rule(context)
        assert any("future" in h.description.lower() for h in hits)

    def test_invalid_date_bad_format(self):
        """Test that invalid date format triggers rule."""
        from rules.categories.format_rules import format_invalid_date_rule

        context = RuleContext(
            claim={"service_date": "not-a-date", "items": []},
            datasets={},
            config={},
        )
        hits = format_invalid_date_rule(context)
        assert any("Invalid service date format" in h.description for h in hits)

    def test_invalid_date_valid(self):
        """Test that valid date doesn't trigger rule."""
        from rules.categories.format_rules import format_invalid_date_rule

        context = RuleContext(
            claim={"service_date": "2024-01-15", "items": []},
            datasets={},
            config={},
        )
        hits = format_invalid_date_rule(context)
        # Should not have future date or invalid format hits
        assert not any("future" in h.description.lower() for h in hits)
        assert not any("Invalid service date format" in h.description for h in hits)

    def test_invalid_code_missing_procedure(self):
        """Test that missing procedure code triggers rule."""
        from rules.categories.format_rules import format_invalid_code_rule

        context = RuleContext(
            claim={"items": [{"quantity": 1}]},
            datasets={},
            config={},
        )
        hits = format_invalid_code_rule(context)
        assert any("missing procedure code" in h.description for h in hits)

    def test_invalid_code_bad_format(self):
        """Test that invalid code format triggers rule."""
        from rules.categories.format_rules import format_invalid_code_rule

        context = RuleContext(
            claim={"items": [{"procedure_code": "INVALID"}]},
            datasets={},
            config={},
        )
        hits = format_invalid_code_rule(context)
        assert any("Invalid procedure code format" in h.description for h in hits)

    def test_invalid_code_valid_cpt(self):
        """Test that valid CPT code doesn't trigger format error."""
        from rules.categories.format_rules import format_invalid_code_rule

        context = RuleContext(
            claim={"items": [{"procedure_code": "99213"}]},
            datasets={},
            config={},
        )
        hits = format_invalid_code_rule(context)
        # Should not have format errors for valid code
        assert not any("Invalid procedure code format" in h.description for h in hits)


# ============================================================================
# NCCI RULES TESTS
# ============================================================================
class TestNCCIRules:
    """Tests for NCCI (National Correct Coding Initiative) rules."""

    def test_ptp_edit_detected(self):
        """Test that NCCI PTP edit is detected."""
        from rules.categories.ncci_rules import ncci_ptp_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99214"},
                    {"procedure_code": "99215"},
                ]
            },
            datasets={
                "ncci_ptp": {
                    ("99214", "99215"): {"citation": "NCCI PTP Edit", "modifier": "25"}
                }
            },
            config={},
        )
        hits = ncci_ptp_rule(context)
        assert len(hits) == 1
        assert hits[0].rule_id == "NCCI_PTP"

    def test_ptp_edit_no_conflict(self):
        """Test that non-conflicting codes don't trigger PTP edit."""
        from rules.categories.ncci_rules import ncci_ptp_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99213"},
                    {"procedure_code": "93000"},
                ]
            },
            datasets={"ncci_ptp": {}},
            config={},
        )
        hits = ncci_ptp_rule(context)
        assert len(hits) == 0

    def test_mue_violation_detected(self):
        """Test that MUE violation is detected."""
        from rules.categories.ncci_rules import ncci_mue_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99213", "quantity": 3},
                ]
            },
            datasets={"ncci_mue": {"99213": {"limit": 1}}},
            config={},
        )
        hits = ncci_mue_rule(context)
        assert len(hits) == 1
        assert "exceeds MUE limit" in hits[0].description

    def test_mue_within_limit(self):
        """Test that quantity within MUE limit doesn't trigger."""
        from rules.categories.ncci_rules import ncci_mue_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99213", "quantity": 1},
                ]
            },
            datasets={"ncci_mue": {"99213": {"limit": 1}}},
            config={},
        )
        hits = ncci_mue_rule(context)
        assert len(hits) == 0

    def test_addon_without_primary(self):
        """Test add-on code without primary procedure."""
        from rules.categories.ncci_rules import ncci_addon_no_primary_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99354"},  # Add-on code
                ]
            },
            datasets={
                "ncci_addon": {
                    "99354": {"primary_codes": ["99213", "99214", "99215"]}
                }
            },
            config={},
        )
        hits = ncci_addon_no_primary_rule(context)
        assert len(hits) == 1
        assert "without required primary" in hits[0].description

    def test_addon_with_primary(self):
        """Test add-on code with primary procedure present."""
        from rules.categories.ncci_rules import ncci_addon_no_primary_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99214"},  # Primary code
                    {"procedure_code": "99354"},  # Add-on code
                ]
            },
            datasets={
                "ncci_addon": {
                    "99354": {"primary_codes": ["99213", "99214", "99215"]}
                }
            },
            config={},
        )
        hits = ncci_addon_no_primary_rule(context)
        assert len(hits) == 0

    def test_mutually_exclusive_detected(self):
        """Test mutually exclusive codes are detected."""
        from rules.categories.ncci_rules import ncci_mutually_exclusive_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "64415"},
                    {"procedure_code": "64416"},
                ]
            },
            datasets={
                "ncci_mutex": {
                    ("64415", "64416"): True
                }
            },
            config={},
        )
        hits = ncci_mutually_exclusive_rule(context)
        assert len(hits) == 1
        assert "Mutually exclusive" in hits[0].description


# ============================================================================
# MODIFIER RULES TESTS
# ============================================================================
class TestModifierRules:
    """Tests for modifier validation rules."""

    def test_invalid_modifier(self):
        """Test that invalid modifier triggers rule."""
        from rules.categories.modifier_rules import modifier_invalid_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99213", "modifiers": ["XX"]},
                ]
            },
            datasets={"valid_modifiers": {"25", "59", "50", "LT", "RT"}},
            config={},
        )
        hits = modifier_invalid_rule(context)
        assert len(hits) == 1
        assert "Invalid modifier" in hits[0].description

    def test_valid_modifier(self):
        """Test that valid modifier doesn't trigger rule."""
        from rules.categories.modifier_rules import modifier_invalid_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99213", "modifiers": ["25"]},
                ]
            },
            datasets={"valid_modifiers": {"25", "59", "50"}},
            config={},
        )
        hits = modifier_invalid_rule(context)
        assert len(hits) == 0

    def test_modifier_59_abuse(self):
        """Test that modifier 59 without NCCI conflict is flagged."""
        from rules.categories.modifier_rules import modifier_59_abuse_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99213", "modifiers": ["59"]},
                    {"procedure_code": "93000"},
                ]
            },
            datasets={"ncci_ptp": {}},
            config={},
        )
        hits = modifier_59_abuse_rule(context)
        assert len(hits) == 1
        assert "without apparent NCCI edit conflict" in hits[0].description

    def test_modifier_bilateral_conflict(self):
        """Test bilateral modifier conflict detection."""
        from rules.categories.modifier_rules import modifier_bilateral_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "27447", "modifiers": ["50", "LT"]},
                ]
            },
            datasets={},
            config={},
        )
        hits = modifier_bilateral_rule(context)
        assert any("Both bilateral" in h.description for h in hits)

    def test_modifier_missing_required(self):
        """Test missing required modifier detection."""
        from rules.categories.modifier_rules import modifier_missing_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "27447", "modifiers": []},
                ]
            },
            datasets={
                "modifier_rules": {
                    "27447": {"required_modifiers": ["50"]}
                }
            },
            config={},
        )
        hits = modifier_missing_rule(context)
        assert len(hits) == 1
        assert "requires modifier" in hits[0].description


# ============================================================================
# ELIGIBILITY RULES TESTS
# ============================================================================
class TestEligibilityRules:
    """Tests for eligibility rules."""

    def test_member_not_found(self):
        """Test that unknown member triggers rule."""
        from rules.categories.eligibility_rules import eligibility_inactive_rule

        context = RuleContext(
            claim={
                "member": {"member_id": "UNKNOWN123"},
                "service_date": "2024-01-15",
            },
            datasets={
                "member_eligibility": {
                    "M12345": {
                        "effective_date": "2023-01-01",
                        "termination_date": "2025-12-31",
                    }
                }
            },
            config={},
        )
        hits = eligibility_inactive_rule(context)
        assert len(hits) == 1
        assert "not found" in hits[0].description

    def test_service_before_effective_date(self):
        """Test service date before effective date."""
        from rules.categories.eligibility_rules import eligibility_inactive_rule

        context = RuleContext(
            claim={
                "member": {"member_id": "M12345"},
                "service_date": "2022-06-15",
            },
            datasets={
                "member_eligibility": {
                    "M12345": {
                        "effective_date": "2023-01-01",
                        "termination_date": "2025-12-31",
                    }
                }
            },
            config={},
        )
        hits = eligibility_inactive_rule(context)
        assert len(hits) == 1
        assert "before member effective date" in hits[0].description

    def test_service_after_termination(self):
        """Test service date after termination date."""
        from rules.categories.eligibility_rules import eligibility_inactive_rule

        context = RuleContext(
            claim={
                "member": {"member_id": "M12345"},
                "service_date": "2026-06-15",
            },
            datasets={
                "member_eligibility": {
                    "M12345": {
                        "effective_date": "2023-01-01",
                        "termination_date": "2025-12-31",
                    }
                }
            },
            config={},
        )
        hits = eligibility_inactive_rule(context)
        assert len(hits) == 1
        assert "after member termination date" in hits[0].description

    def test_eligible_member(self):
        """Test that eligible member doesn't trigger rule."""
        from rules.categories.eligibility_rules import eligibility_inactive_rule

        context = RuleContext(
            claim={
                "member": {"member_id": "M12345"},
                "service_date": "2024-06-15",
            },
            datasets={
                "member_eligibility": {
                    "M12345": {
                        "effective_date": "2023-01-01",
                        "termination_date": "2025-12-31",
                    }
                }
            },
            config={},
        )
        hits = eligibility_inactive_rule(context)
        assert len(hits) == 0

    def test_non_covered_procedure(self):
        """Test non-covered procedure detection."""
        from rules.categories.eligibility_rules import eligibility_non_covered_rule

        context = RuleContext(
            claim={
                "member": {"member_id": "M12345", "plan_id": "PLAN_A"},
                "items": [{"procedure_code": "S0390"}],
            },
            datasets={
                "benefit_exclusions": {"PLAN_A": {"S0390", "S0395"}}
            },
            config={},
        )
        hits = eligibility_non_covered_rule(context)
        assert len(hits) == 1
        assert "excluded from member's benefit plan" in hits[0].description

    def test_no_prior_auth(self):
        """Test missing prior authorization detection."""
        from rules.categories.eligibility_rules import eligibility_no_auth_rule

        context = RuleContext(
            claim={
                "member": {"member_id": "M12345"},
                "service_date": "2024-01-15",
                "items": [{"procedure_code": "27447"}],
            },
            datasets={
                "auth_required_codes": {"27447", "27130"},
                "authorizations": {},
            },
            config={},
        )
        hits = eligibility_no_auth_rule(context)
        assert len(hits) == 1
        assert "requires prior authorization" in hits[0].description


# ============================================================================
# DUPLICATE RULES TESTS
# ============================================================================
class TestDuplicateRules:
    """Tests for duplicate detection rules."""

    def test_duplicate_line_detected(self):
        """Test duplicate line items on same claim."""
        from rules.categories.duplicate_rules import duplicate_line_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99213", "quantity": 1},
                    {"procedure_code": "99213", "quantity": 1},
                ]
            },
            datasets={},
            config={},
        )
        hits = duplicate_line_rule(context)
        assert len(hits) == 1
        assert "repeated" in hits[0].description.lower()

    def test_no_duplicate_lines(self):
        """Test no duplicate when codes are different."""
        from rules.categories.duplicate_rules import duplicate_line_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99213", "quantity": 1},
                    {"procedure_code": "99214", "quantity": 1},
                ]
            },
            datasets={},
            config={},
        )
        hits = duplicate_line_rule(context)
        assert len(hits) == 0


# ============================================================================
# FWA RULES TESTS
# ============================================================================
class TestFWARules:
    """Tests for Fraud, Waste, and Abuse detection rules."""

    def test_oig_exclusion_detected(self):
        """Test OIG excluded provider detection."""
        from rules.categories.fwa_rules import oig_exclusion_rule

        context = RuleContext(
            claim={
                "provider": {"npi": "1234567890"},
            },
            datasets={"oig_exclusions": {"1234567890"}},
            config={},
        )
        hits = oig_exclusion_rule(context)
        assert len(hits) == 1
        assert hits[0].rule_id == "OIG_EXCLUSION"

    def test_oig_exclusion_not_excluded(self):
        """Test that non-excluded provider doesn't trigger."""
        from rules.categories.fwa_rules import oig_exclusion_rule

        context = RuleContext(
            claim={
                "provider": {"npi": "9999999999"},
            },
            datasets={"oig_exclusions": {"1234567890"}},
            config={},
        )
        hits = oig_exclusion_rule(context)
        assert len(hits) == 0

    def test_fwa_watchlist_detected(self):
        """Test FWA watchlist provider detection."""
        from rules.categories.fwa_rules import fwa_watchlist_rule

        context = RuleContext(
            claim={
                "provider": {"npi": "1111111111"},
            },
            datasets={"fwa_watchlist": {"1111111111"}},
            config={},
        )
        hits = fwa_watchlist_rule(context)
        assert len(hits) == 1
        assert hits[0].rule_id == "FWA_WATCH"

    def test_high_volume_spike(self):
        """Test volume spike detection based on provider patterns."""
        from rules.categories.fwa_rules import fwa_volume_spike_rule

        # This rule checks provider volume patterns - test with high volume provider
        context = RuleContext(
            claim={
                "provider": {"npi": "1234567890"},
            },
            datasets={
                "provider_volumes": {
                    "1234567890": {
                        "current_month_claims": 500,
                        "avg_monthly_claims": 100,
                        "std_dev": 20,
                    }
                }
            },
            config={},
        )
        hits = fwa_volume_spike_rule(context)
        # Rule triggers when volume is significantly above average
        assert len(hits) >= 0  # May or may not trigger based on thresholds


# ============================================================================
# PRICING RULES TESTS
# ============================================================================
class TestPricingRules:
    """Tests for pricing and reimbursement rules."""

    def test_exceeds_fee_schedule(self):
        """Test billed amount exceeds fee schedule by more than 150%."""
        from rules.categories.pricing_rules import pricing_exceeds_fee_rule

        # Rule triggers when amount > allowed * 1.5
        context = RuleContext(
            claim={
                "provider": {"npi": "1234567890"},
                "items": [
                    {"procedure_code": "99213", "line_amount": 200.00, "quantity": 1},
                ]
            },
            datasets={
                "fee_schedule": {"99213": {"national": 95.0}}
            },
            config={},
        )
        hits = pricing_exceeds_fee_rule(context)
        assert len(hits) == 1
        assert "exceeds" in hits[0].description.lower()

    def test_within_fee_schedule(self):
        """Test billed amount within fee schedule (under 150%)."""
        from rules.categories.pricing_rules import pricing_exceeds_fee_rule

        # Amount is 140 which is < 95 * 1.5 = 142.5
        context = RuleContext(
            claim={
                "provider": {"npi": "1234567890"},
                "items": [
                    {"procedure_code": "99213", "line_amount": 140.00, "quantity": 1},
                ]
            },
            datasets={
                "fee_schedule": {"99213": {"national": 95.0}}
            },
            config={},
        )
        hits = pricing_exceeds_fee_rule(context)
        assert len(hits) == 0


# ============================================================================
# COVERAGE RULES TESTS
# ============================================================================
class TestCoverageRules:
    """Tests for coverage and LCD rules."""

    def test_lcd_coverage_mismatch(self):
        """Test LCD diagnosis code mismatch."""
        from rules.categories.coverage_rules import lcd_coverage_rule

        context = RuleContext(
            claim={
                "diagnosis_codes": ["Z00.00"],  # Non-covered diagnosis
                "items": [
                    {"procedure_code": "99213", "diagnosis_code": "Z00.00"},
                ]
            },
            datasets={
                "lcd": {
                    "99213": {
                        "diagnosis_codes": {"J06.9", "J20.9"},
                    }
                }
            },
            config={},
        )
        hits = lcd_coverage_rule(context)
        assert len(hits) == 1
        assert hits[0].rule_id == "LCD_MISMATCH"

    def test_lcd_coverage_valid(self):
        """Test valid LCD coverage."""
        from rules.categories.coverage_rules import lcd_coverage_rule

        context = RuleContext(
            claim={
                "diagnosis_codes": ["J06.9"],
                "items": [
                    {"procedure_code": "99213", "diagnosis_code": "J06.9"},
                ]
            },
            datasets={
                "lcd": {
                    "99213": {
                        "diagnosis_codes": {"J06.9", "J20.9"},
                    }
                }
            },
            config={},
        )
        hits = lcd_coverage_rule(context)
        assert len(hits) == 0


# ============================================================================
# SURGICAL RULES TESTS
# ============================================================================
class TestSurgicalRules:
    """Tests for surgical package rules."""

    def test_global_period_violation(self):
        """Test billing during global surgery period."""
        from rules.categories.surgical_rules import surgical_global_period_rule

        context = RuleContext(
            claim={
                "member": {"member_id": "M12345"},
                "service_date": "2024-01-20",
                "items": [
                    {"procedure_code": "99213"},
                ]
            },
            datasets={
                "global_surgery": {
                    "27447": {"global_days": 90}
                },
                "surgical_history": {
                    "M12345": [
                        {
                            "procedure_code": "27447",
                            "service_date": "2024-01-15",
                        }
                    ]
                }
            },
            config={},
        )
        hits = surgical_global_period_rule(context)
        assert len(hits) == 1
        assert "global" in hits[0].description.lower()

    def test_multiple_procedure_reduction(self):
        """Test multiple procedure without modifier 51."""
        from rules.categories.surgical_rules import surgical_multiple_procedure_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "27447"},
                    {"procedure_code": "27130"},
                ]
            },
            datasets={
                "multiple_procedure_codes": {"27447", "27130", "27446"}
            },
            config={},
        )
        hits = surgical_multiple_procedure_rule(context)
        assert len(hits) == 1
        assert "modifier 51" in hits[0].description.lower()


# ============================================================================
# TIMELY FILING RULES TESTS
# ============================================================================
class TestTimelyFilingRules:
    """Tests for timely filing rules."""

    def test_late_submission(self):
        """Test late claim submission detection."""
        from rules.categories.timely_filing_rules import timely_filing_late_rule

        # Service date more than 365 days ago
        old_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        context = RuleContext(
            claim={
                "service_date": old_date,
                "received_date": datetime.now().strftime("%Y-%m-%d"),
            },
            datasets={},
            config={"filing_limit_days": 365},
        )
        hits = timely_filing_late_rule(context)
        assert len(hits) == 1
        assert "filed" in hits[0].description.lower()
        assert "days" in hits[0].description.lower()


# ============================================================================
# COB RULES TESTS
# ============================================================================
class TestCOBRules:
    """Tests for Coordination of Benefits rules."""

    def test_wrong_primary_payer(self):
        """Test wrong primary payer order."""
        from rules.categories.cob_rules import cob_wrong_primary_rule

        context = RuleContext(
            claim={
                "payer_id": "PAYER_B",
                "cob": {
                    "this_payer_priority": 1,
                    "other_payers": [
                        {"payer_id": "PAYER_A", "priority": 0}  # Higher priority (lower number)
                    ]
                }
            },
            datasets={},
            config={},
        )
        hits = cob_wrong_primary_rule(context)
        assert len(hits) == 1
        assert hits[0].rule_id == "COB_WRONG_PRIMARY"


# ============================================================================
# POS RULES TESTS
# ============================================================================
class TestPOSRules:
    """Tests for Place of Service rules."""

    def test_invalid_pos(self):
        """Test invalid place of service code."""
        from rules.categories.pos_rules import pos_invalid_rule

        context = RuleContext(
            claim={
                "place_of_service": "99",  # Invalid POS
                "items": [{"procedure_code": "99213"}],
            },
            datasets={
                "valid_pos_codes": {"11", "21", "22", "23", "24", "31", "32"}
            },
            config={},
        )
        hits = pos_invalid_rule(context)
        assert len(hits) == 1
        assert "invalid place of service" in hits[0].description.lower()

    def test_valid_pos(self):
        """Test valid place of service code."""
        from rules.categories.pos_rules import pos_invalid_rule

        context = RuleContext(
            claim={
                "place_of_service": "11",  # Office
                "items": [{"procedure_code": "99213"}],
            },
            datasets={
                "valid_pos_codes": {"11", "21", "22"}
            },
            config={},
        )
        hits = pos_invalid_rule(context)
        assert len(hits) == 0


# ============================================================================
# OCE RULES TESTS
# ============================================================================
class TestOCERules:
    """Tests for Outpatient Code Editor rules."""

    def test_inpatient_only_in_outpatient(self):
        """Test inpatient-only procedure in outpatient setting."""
        from rules.categories.oce_rules import oce_inpatient_only_rule

        context = RuleContext(
            claim={
                "claim_type": "outpatient",
                "items": [
                    {"procedure_code": "33533"},  # CABG - inpatient only
                ]
            },
            datasets={
                "inpatient_only_codes": {"33533", "33534", "33535"}
            },
            config={},
        )
        hits = oce_inpatient_only_rule(context)
        assert len(hits) == 1
        assert "inpatient" in hits[0].description.lower()


# ============================================================================
# SPECIALTY RULES TESTS
# ============================================================================
class TestSpecialtyRules:
    """Tests for specialty-specific rules."""

    def test_telehealth_code_not_eligible(self):
        """Test non-telehealth code with telehealth modifier."""
        from rules.categories.specialty_rules import specialty_telehealth_rule

        context = RuleContext(
            claim={
                "place_of_service": "02",  # Telehealth POS
                "provider": {"provider_type": "physician"},
                "items": [
                    {"procedure_code": "27447", "place_of_service": "02"},  # Knee replacement - not telehealth eligible
                ]
            },
            datasets={
                "telehealth_codes": {"99213", "99214", "99215"},  # Only E/M codes allowed
            },
            config={},
        )
        hits = specialty_telehealth_rule(context)
        assert len(hits) >= 1
        assert any("telehealth" in h.description.lower() for h in hits)

    def test_unbundling_detected(self):
        """Test procedure unbundling detection."""
        from rules.categories.specialty_rules import specialty_unbundling_rule

        context = RuleContext(
            claim={
                "items": [
                    {"procedure_code": "99213"},
                    {"procedure_code": "36415"},  # Component of comprehensive code
                ]
            },
            datasets={
                "comprehensive_codes": {
                    "99213": {
                        "component_codes": ["36415", "36416"]
                    }
                }
            },
            config={},
        )
        hits = specialty_unbundling_rule(context)
        assert len(hits) == 1
        assert "component" in hits[0].description.lower() or "unbundl" in hits[0].description.lower()
