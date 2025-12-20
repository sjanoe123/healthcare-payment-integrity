"""Healthcare fraud detection rules.

This module provides backward compatibility by re-exporting rules from
the new category-based organization in backend/rules/categories/.
"""

from __future__ import annotations

from collections.abc import Callable

from .models import RuleContext, RuleHit
from .registry import RuleRegistry

# Import all rules from category modules
from .categories.ncci_rules import (
    ncci_ptp_rule,
    ncci_mue_rule,
    ncci_addon_no_primary_rule,
    ncci_mutually_exclusive_rule,
)
from .categories.coverage_rules import (
    lcd_coverage_rule,
    lcd_age_gender_rule,
    lcd_experimental_rule,
    global_surgery_modifier_rule,
)
from .categories.provider_rules import (
    provider_outlier_rule,
)
from .categories.financial_rules import (
    high_dollar_rule,
    reimbursement_outlier_rule,
    misc_code_rule,
)
from .categories.fwa_rules import (
    oig_exclusion_rule,
    fwa_watchlist_rule,
    fwa_volume_spike_rule,
    fwa_pattern_rule,
)
from .categories.duplicate_rules import (
    duplicate_line_rule,
    duplicate_exact_rule,
    duplicate_same_day_rule,
    duplicate_cross_claim_rule,
)
from .categories.format_rules import (
    format_missing_field_rule,
    format_invalid_date_rule,
    format_invalid_code_rule,
)
from .categories.eligibility_rules import (
    eligibility_inactive_rule,
    eligibility_non_covered_rule,
    eligibility_benefit_limit_rule,
    eligibility_no_auth_rule,
)
from .categories.timely_filing_rules import (
    timely_filing_late_rule,
    timely_filing_no_exception_rule,
)
from .categories.cob_rules import (
    cob_wrong_primary_rule,
    cob_incomplete_rule,
)
from .categories.modifier_rules import (
    modifier_invalid_rule,
    modifier_missing_rule,
    modifier_59_abuse_rule,
    modifier_bilateral_rule,
)
from .categories.pos_rules import (
    pos_invalid_rule,
    pos_provider_mismatch_rule,
)
from .categories.pricing_rules import (
    pricing_exceeds_fee_rule,
    pricing_units_exceed_rule,
    pricing_drg_mismatch_rule,
    pricing_revenue_code_rule,
)
from .categories.necessity_rules import (
    necessity_experimental_rule,
    necessity_frequency_rule,
)
from .categories.oce_rules import (
    oce_revenue_code_rule,
    oce_inpatient_only_rule,
    oce_observation_hours_rule,
)
from .categories.specialty_rules import (
    specialty_dental_rule,
    specialty_dme_rule,
    specialty_telehealth_rule,
    specialty_unbundling_rule,
    specialty_incidental_rule,
)
from .categories.surgical_rules import (
    surgical_global_period_rule,
    surgical_multiple_procedure_rule,
    surgical_assistant_rule,
    surgical_cosurgeon_rule,
    surgical_bilateral_rule,
)

Rule = Callable[[RuleContext], list[RuleHit]]


def register_default_rules(registry: RuleRegistry) -> None:
    """Register all default fraud detection rules.

    Rules are organized by priority:
    1. Critical compliance rules (format, eligibility)
    2. Regulatory rules (NCCI, coverage)
    3. Financial rules (pricing, duplicates)
    4. FWA detection rules
    """
    registry.extend(
        [
            # Format & Basic Validation (run first for early rejection)
            format_missing_field_rule,
            format_invalid_date_rule,
            format_invalid_code_rule,

            # Eligibility & Coverage
            eligibility_inactive_rule,
            eligibility_non_covered_rule,
            eligibility_benefit_limit_rule,
            eligibility_no_auth_rule,

            # Timely Filing
            timely_filing_late_rule,
            timely_filing_no_exception_rule,

            # Duplicate Detection
            duplicate_exact_rule,
            duplicate_same_day_rule,
            duplicate_cross_claim_rule,
            duplicate_line_rule,

            # Coordination of Benefits
            cob_wrong_primary_rule,
            cob_incomplete_rule,

            # NCCI Edits
            ncci_ptp_rule,
            ncci_mue_rule,
            ncci_addon_no_primary_rule,
            ncci_mutually_exclusive_rule,

            # Modifier Validation
            modifier_invalid_rule,
            modifier_missing_rule,
            modifier_59_abuse_rule,
            modifier_bilateral_rule,

            # Place of Service
            pos_invalid_rule,
            pos_provider_mismatch_rule,

            # Pricing & Reimbursement
            high_dollar_rule,
            reimbursement_outlier_rule,
            pricing_exceeds_fee_rule,
            pricing_units_exceed_rule,
            pricing_drg_mismatch_rule,
            pricing_revenue_code_rule,

            # Medical Necessity
            lcd_coverage_rule,
            lcd_age_gender_rule,
            lcd_experimental_rule,
            global_surgery_modifier_rule,
            necessity_experimental_rule,
            necessity_frequency_rule,

            # FWA Detection
            oig_exclusion_rule,
            fwa_watchlist_rule,
            fwa_volume_spike_rule,
            fwa_pattern_rule,
            provider_outlier_rule,

            # OCE Edits
            oce_revenue_code_rule,
            oce_inpatient_only_rule,
            oce_observation_hours_rule,

            # Specialty Rules
            specialty_dental_rule,
            specialty_dme_rule,
            specialty_telehealth_rule,
            specialty_unbundling_rule,
            specialty_incidental_rule,

            # Surgical Package
            surgical_global_period_rule,
            surgical_multiple_procedure_rule,
            surgical_assistant_rule,
            surgical_cosurgeon_rule,
            surgical_bilateral_rule,

            # Misc
            misc_code_rule,
        ]
    )


# Export all rules for backward compatibility
__all__ = [
    "register_default_rules",
    "Rule",
    # Format rules
    "format_missing_field_rule",
    "format_invalid_date_rule",
    "format_invalid_code_rule",
    # Eligibility rules
    "eligibility_inactive_rule",
    "eligibility_non_covered_rule",
    "eligibility_benefit_limit_rule",
    "eligibility_no_auth_rule",
    # Timely filing rules
    "timely_filing_late_rule",
    "timely_filing_no_exception_rule",
    # Duplicate rules
    "duplicate_exact_rule",
    "duplicate_same_day_rule",
    "duplicate_cross_claim_rule",
    "duplicate_line_rule",
    # COB rules
    "cob_wrong_primary_rule",
    "cob_incomplete_rule",
    # NCCI rules
    "ncci_ptp_rule",
    "ncci_mue_rule",
    "ncci_addon_no_primary_rule",
    "ncci_mutually_exclusive_rule",
    # Modifier rules
    "modifier_invalid_rule",
    "modifier_missing_rule",
    "modifier_59_abuse_rule",
    "modifier_bilateral_rule",
    # POS rules
    "pos_invalid_rule",
    "pos_provider_mismatch_rule",
    # Pricing rules
    "high_dollar_rule",
    "reimbursement_outlier_rule",
    "pricing_exceeds_fee_rule",
    "pricing_units_exceed_rule",
    "pricing_drg_mismatch_rule",
    "pricing_revenue_code_rule",
    # Coverage rules
    "lcd_coverage_rule",
    "lcd_age_gender_rule",
    "lcd_experimental_rule",
    "global_surgery_modifier_rule",
    # Necessity rules
    "necessity_experimental_rule",
    "necessity_frequency_rule",
    # FWA rules
    "oig_exclusion_rule",
    "fwa_watchlist_rule",
    "fwa_volume_spike_rule",
    "fwa_pattern_rule",
    # Provider rules
    "provider_outlier_rule",
    # OCE rules
    "oce_revenue_code_rule",
    "oce_inpatient_only_rule",
    "oce_observation_hours_rule",
    # Specialty rules
    "specialty_dental_rule",
    "specialty_dme_rule",
    "specialty_telehealth_rule",
    "specialty_unbundling_rule",
    "specialty_incidental_rule",
    # Surgical rules
    "surgical_global_period_rule",
    "surgical_multiple_procedure_rule",
    "surgical_assistant_rule",
    "surgical_cosurgeon_rule",
    "surgical_bilateral_rule",
    # Misc
    "misc_code_rule",
]
