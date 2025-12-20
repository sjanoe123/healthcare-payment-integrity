"""Healthcare fraud detection rules organized by category."""

from __future__ import annotations

from .coverage_rules import (
    global_surgery_modifier_rule,
    lcd_age_gender_rule,
    lcd_coverage_rule,
    lcd_experimental_rule,
)
from .duplicate_rules import (
    duplicate_cross_claim_rule,
    duplicate_exact_rule,
    duplicate_line_rule,
    duplicate_same_day_rule,
)
from .eligibility_rules import (
    eligibility_benefit_limit_rule,
    eligibility_inactive_rule,
    eligibility_no_auth_rule,
    eligibility_non_covered_rule,
)
from .financial_rules import (
    high_dollar_rule,
    misc_code_rule,
    reimbursement_outlier_rule,
)
from .format_rules import (
    format_invalid_code_rule,
    format_invalid_date_rule,
    format_missing_field_rule,
)
from .fwa_rules import (
    fwa_pattern_rule,
    fwa_volume_spike_rule,
    fwa_watchlist_rule,
    oig_exclusion_rule,
)
from .modifier_rules import (
    modifier_59_abuse_rule,
    modifier_bilateral_rule,
    modifier_invalid_rule,
    modifier_missing_rule,
)
from .ncci_rules import (
    ncci_addon_no_primary_rule,
    ncci_mue_rule,
    ncci_mutually_exclusive_rule,
    ncci_ptp_rule,
)
from .necessity_rules import (
    necessity_experimental_rule,
    necessity_frequency_rule,
)
from .oce_rules import (
    oce_inpatient_only_rule,
    oce_observation_hours_rule,
    oce_revenue_code_rule,
)
from .pos_rules import (
    pos_invalid_rule,
    pos_provider_mismatch_rule,
)
from .pricing_rules import (
    pricing_drg_mismatch_rule,
    pricing_exceeds_fee_rule,
    pricing_revenue_code_rule,
    pricing_units_exceed_rule,
)
from .provider_rules import (
    provider_outlier_rule,
)
from .specialty_rules import (
    specialty_dental_rule,
    specialty_dme_rule,
    specialty_incidental_rule,
    specialty_telehealth_rule,
    specialty_unbundling_rule,
)
from .surgical_rules import (
    surgical_assistant_rule,
    surgical_bilateral_rule,
    surgical_cosurgeon_rule,
    surgical_global_period_rule,
    surgical_multiple_procedure_rule,
)
from .timely_filing_rules import (
    timely_filing_late_rule,
    timely_filing_no_exception_rule,
)
from .cob_rules import (
    cob_incomplete_rule,
    cob_wrong_primary_rule,
)

__all__ = [
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
    "pricing_exceeds_fee_rule",
    "pricing_units_exceed_rule",
    "pricing_drg_mismatch_rule",
    "pricing_revenue_code_rule",
    # Medical necessity rules
    "necessity_experimental_rule",
    "necessity_frequency_rule",
    # FWA rules
    "oig_exclusion_rule",
    "fwa_watchlist_rule",
    "fwa_volume_spike_rule",
    "fwa_pattern_rule",
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
    # Coverage rules
    "lcd_coverage_rule",
    "lcd_age_gender_rule",
    "lcd_experimental_rule",
    "global_surgery_modifier_rule",
    # Provider rules
    "provider_outlier_rule",
    # Financial rules
    "high_dollar_rule",
    "reimbursement_outlier_rule",
    "misc_code_rule",
]
