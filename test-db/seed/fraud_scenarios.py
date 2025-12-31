"""
Fraud Scenario Generator for Healthcare Payment Integrity Test Data.

Generates claims with specific fraud patterns aligned with the rules engine:
- backend/rules/categories/ncci_rules.py
- backend/rules/categories/fwa_rules.py
- backend/rules/categories/pricing_rules.py
- backend/rules/categories/eligibility_rules.py
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any, Optional

try:
    from .reference_loader import ReferenceDataLoader, MPFSEntry, MUEEntry, PTPEntry
    from .utils import random_diagnosis, random_pos
except ImportError:
    from reference_loader import ReferenceDataLoader, MPFSEntry, MUEEntry, PTPEntry
    from utils import random_diagnosis, random_pos


class FraudScenarioType(Enum):
    """Types of fraud scenarios."""
    # High-risk (15%)
    OIG_EXCLUDED = "oig_excluded"
    NCCI_PTP_VIOLATION = "ncci_ptp_violation"
    NCCI_MUE_VIOLATION = "ncci_mue_violation"
    FEE_SCHEDULE_OUTLIER = "fee_schedule_outlier"
    MISSING_AUTHORIZATION = "missing_authorization"
    POLICY_VIOLATION = "policy_violation"

    # Medium-risk (25%)
    BORDERLINE_FEE = "borderline_fee"
    NEAR_MUE_LIMIT = "near_mue_limit"
    CODING_ISSUE = "coding_issue"
    NEAR_DUPLICATE = "near_duplicate"
    VOLUME_SPIKE = "volume_spike"

    # Clean (60%)
    CLEAN = "clean"


@dataclass
class ClaimLine:
    """Represents a claim service line."""
    line_number: int
    procedure_code: str
    units: float = 1.0
    line_charge: float = 0.0
    modifier_1: Optional[str] = None
    modifier_2: Optional[str] = None
    service_date: Optional[date] = None
    place_of_service: str = "11"
    diagnosis_pointer: list[int] = field(default_factory=lambda: [1])


@dataclass
class ClaimData:
    """Represents claim data to be inserted."""
    claim_id: str
    member_id: str
    billing_provider_npi: str
    statement_from_date: date
    claim_type: str = "837P"
    place_of_service: str = "11"
    diagnosis_codes: list[str] = field(default_factory=list)
    lines: list[ClaimLine] = field(default_factory=list)
    total_charge: float = 0.0
    scenario_type: FraudScenarioType = FraudScenarioType.CLEAN
    scenario_details: dict = field(default_factory=dict)

    def calculate_total(self):
        """Calculate total charge from lines."""
        self.total_charge = sum(line.line_charge for line in self.lines)


class FraudScenarioGenerator:
    """Generates claims with specific fraud patterns."""

    def __init__(self, reference_data: ReferenceDataLoader):
        """
        Initialize the fraud scenario generator.

        Args:
            reference_data: Loaded reference data (NCCI, MPFS, OIG)
        """
        self.ref = reference_data

        # Pre-load samples for each scenario type
        self._ptp_pairs: list[PTPEntry] = []
        self._mue_codes: list[MUEEntry] = []
        self._priced_codes: list[tuple[str, MPFSEntry]] = []
        self._oig_npis: list[str] = []

        # Authorization-required codes (high-cost procedures)
        self._auth_required_codes: set[str] = set()

        self._initialize_samples()

    def _initialize_samples(self):
        """Pre-load random samples for scenario generation."""
        # Get 500 random PTP pairs
        self._ptp_pairs = self.ref.get_random_ptp_pairs(500)

        # Get 200 random MUE codes with limits
        self._mue_codes = self.ref.get_random_mue_codes(200)

        # Get 300 random priced codes
        self._priced_codes = self.ref.get_random_priced_codes(300)

        # Get 50 OIG excluded NPIs
        self._oig_npis = self.ref.get_random_oig_excluded_npis(50)

        # Define auth-required codes (typically high-cost procedures)
        self._auth_required_codes = {
            # Surgery
            "27447", "27130", "22551", "22612", "63047",
            # Imaging
            "70553", "72148", "74177",
            # Infusions
            "96413", "96365",
            # DME
            "E0470", "E0601", "E1390",
            # Specialty
            "77385", "77386",  # Radiation therapy
            "90867", "90868",  # TMS
        }

        print(f"Initialized fraud scenario generator with:")
        print(f"  - {len(self._ptp_pairs)} PTP pairs")
        print(f"  - {len(self._mue_codes)} MUE codes")
        print(f"  - {len(self._priced_codes)} priced codes")
        print(f"  - {len(self._oig_npis)} OIG excluded NPIs")
        print(f"  - {len(self._auth_required_codes)} auth-required codes")

    # =====================================================
    # HIGH-RISK SCENARIOS (15%)
    # =====================================================

    def create_oig_excluded_claim(
        self,
        claim: ClaimData,
        excluded_npis: list[str],
    ) -> ClaimData:
        """
        Assign claim to an OIG-excluded provider.

        Triggers: OIG_EXCLUSION rule
        """
        if excluded_npis:
            claim.billing_provider_npi = random.choice(excluded_npis)
            claim.scenario_type = FraudScenarioType.OIG_EXCLUDED
            claim.scenario_details["excluded_npi"] = claim.billing_provider_npi

        # Add a normal service line
        code, mpfs = random.choice(self._priced_codes) if self._priced_codes else ("99213", None)
        rate = mpfs.medicare_rate if mpfs else 150.0
        claim.lines.append(ClaimLine(
            line_number=1,
            procedure_code=code,
            units=1,
            line_charge=rate * random.uniform(0.9, 1.1),
            place_of_service=claim.place_of_service,
            service_date=claim.statement_from_date,
        ))

        return claim

    def create_ncci_ptp_violation(self, claim: ClaimData) -> ClaimData:
        """
        Add mutually exclusive procedure codes (column 1/2 pairs).

        Triggers: NCCI_PTP rule
        """
        if not self._ptp_pairs:
            return self._add_clean_lines(claim)

        # Select a PTP pair
        ptp = random.choice(self._ptp_pairs)

        # Add both codes on same claim - creates PTP violation
        charge1 = random.uniform(100, 500)
        charge2 = random.uniform(100, 500)

        claim.lines.extend([
            ClaimLine(
                line_number=1,
                procedure_code=ptp.column1,
                units=1,
                line_charge=charge1,
                place_of_service=claim.place_of_service,
                service_date=claim.statement_from_date,
            ),
            ClaimLine(
                line_number=2,
                procedure_code=ptp.column2,
                units=1,
                line_charge=charge2,
                place_of_service=claim.place_of_service,
                service_date=claim.statement_from_date,
            ),
        ])

        claim.scenario_type = FraudScenarioType.NCCI_PTP_VIOLATION
        claim.scenario_details["ptp_pair"] = (ptp.column1, ptp.column2)
        claim.scenario_details["modifier_indicator"] = ptp.modifier

        return claim

    def create_ncci_mue_violation(self, claim: ClaimData) -> ClaimData:
        """
        Exceed MUE unit limits.

        Triggers: NCCI_MUE rule
        """
        if not self._mue_codes:
            return self._add_clean_lines(claim)

        # Select a code with an MUE limit
        mue = random.choice(self._mue_codes)

        # Exceed the limit by 50-200%
        excess_units = int(mue.limit * random.uniform(1.5, 3.0))
        unit_charge = random.uniform(50, 200)

        claim.lines.append(ClaimLine(
            line_number=1,
            procedure_code=mue.code,
            units=excess_units,
            line_charge=unit_charge * excess_units,
            place_of_service=claim.place_of_service,
            service_date=claim.statement_from_date,
        ))

        claim.scenario_type = FraudScenarioType.NCCI_MUE_VIOLATION
        claim.scenario_details["mue_code"] = mue.code
        claim.scenario_details["mue_limit"] = mue.limit
        claim.scenario_details["billed_units"] = excess_units

        return claim

    def create_fee_schedule_outlier(self, claim: ClaimData) -> ClaimData:
        """
        Bill significantly above Medicare rates (>200%).

        Triggers: PRICING_EXCEEDS_FEE rule
        """
        if not self._priced_codes:
            return self._add_clean_lines(claim)

        # Select a code with pricing
        code, mpfs = random.choice(self._priced_codes)
        medicare_rate = mpfs.medicare_rate

        # Bill 200-400% above Medicare
        inflated_charge = medicare_rate * random.uniform(2.0, 4.0)

        claim.lines.append(ClaimLine(
            line_number=1,
            procedure_code=code,
            units=1,
            line_charge=inflated_charge,
            place_of_service=claim.place_of_service,
            service_date=claim.statement_from_date,
        ))

        claim.scenario_type = FraudScenarioType.FEE_SCHEDULE_OUTLIER
        claim.scenario_details["procedure_code"] = code
        claim.scenario_details["medicare_rate"] = medicare_rate
        claim.scenario_details["billed_amount"] = inflated_charge
        claim.scenario_details["ratio"] = inflated_charge / medicare_rate

        return claim

    def create_missing_auth_claim(self, claim: ClaimData) -> ClaimData:
        """
        Bill auth-required code without authorization.

        Triggers: ELIGIBILITY_NO_AUTH rule
        """
        if not self._auth_required_codes:
            return self._add_clean_lines(claim)

        # Select an auth-required code
        code = random.choice(list(self._auth_required_codes))

        # Get pricing if available
        mpfs = self.ref.mpfs.get(code)
        charge = mpfs.medicare_rate if mpfs else random.uniform(500, 2000)

        claim.lines.append(ClaimLine(
            line_number=1,
            procedure_code=code,
            units=1,
            line_charge=charge,
            place_of_service=claim.place_of_service,
            service_date=claim.statement_from_date,
        ))

        claim.scenario_type = FraudScenarioType.MISSING_AUTHORIZATION
        claim.scenario_details["auth_required_code"] = code
        claim.scenario_details["no_auth_on_file"] = True

        return claim

    def create_policy_violation(self, claim: ClaimData) -> ClaimData:
        """
        Create a claim that violates coverage policies.

        Triggers: LCD/policy-based rules (RAG detection)
        """
        # Use experimental/investigational codes or age-inappropriate services
        experimental_codes = ["0075T", "0076T", "0464T", "0465T"]
        pediatric_codes = ["99381", "99382", "99391", "99392"]  # Well-child visits

        if random.random() < 0.5:
            # Experimental code
            code = random.choice(experimental_codes)
            claim.scenario_details["violation_type"] = "experimental"
        else:
            # Age-inappropriate (pediatric code for adult)
            code = random.choice(pediatric_codes)
            claim.scenario_details["violation_type"] = "age_inappropriate"

        claim.lines.append(ClaimLine(
            line_number=1,
            procedure_code=code,
            units=1,
            line_charge=random.uniform(100, 300),
            place_of_service=claim.place_of_service,
            service_date=claim.statement_from_date,
        ))

        claim.scenario_type = FraudScenarioType.POLICY_VIOLATION
        claim.scenario_details["procedure_code"] = code

        return claim

    # =====================================================
    # MEDIUM-RISK SCENARIOS (25%)
    # =====================================================

    def create_borderline_fee(self, claim: ClaimData) -> ClaimData:
        """
        Bill 110-150% of Medicare - suspicious but not definitive.

        May trigger: PRICING_EXCEEDS_FEE with lower confidence
        """
        if not self._priced_codes:
            return self._add_clean_lines(claim)

        code, mpfs = random.choice(self._priced_codes)
        medicare_rate = mpfs.medicare_rate

        # Bill 110-145% of Medicare
        slightly_inflated = medicare_rate * random.uniform(1.1, 1.45)

        claim.lines.append(ClaimLine(
            line_number=1,
            procedure_code=code,
            units=1,
            line_charge=slightly_inflated,
            place_of_service=claim.place_of_service,
            service_date=claim.statement_from_date,
        ))

        claim.scenario_type = FraudScenarioType.BORDERLINE_FEE
        claim.scenario_details["procedure_code"] = code
        claim.scenario_details["medicare_rate"] = medicare_rate
        claim.scenario_details["billed_amount"] = slightly_inflated

        return claim

    def create_near_mue_limit(self, claim: ClaimData) -> ClaimData:
        """
        Bill exactly at MUE limit - requires scrutiny.
        """
        if not self._mue_codes:
            return self._add_clean_lines(claim)

        mue = random.choice(self._mue_codes)
        unit_charge = random.uniform(50, 200)

        claim.lines.append(ClaimLine(
            line_number=1,
            procedure_code=mue.code,
            units=mue.limit,  # Exactly at limit
            line_charge=unit_charge * mue.limit,
            place_of_service=claim.place_of_service,
            service_date=claim.statement_from_date,
        ))

        claim.scenario_type = FraudScenarioType.NEAR_MUE_LIMIT
        claim.scenario_details["mue_code"] = mue.code
        claim.scenario_details["mue_limit"] = mue.limit
        claim.scenario_details["billed_units"] = mue.limit

        return claim

    def create_coding_issue(self, claim: ClaimData) -> ClaimData:
        """
        Create minor coding issues (missing modifiers, diagnosis mismatch).
        """
        if not self._priced_codes:
            return self._add_clean_lines(claim)

        code, mpfs = random.choice(self._priced_codes)

        # Create a claim with potential modifier issues
        claim.lines.append(ClaimLine(
            line_number=1,
            procedure_code=code,
            units=1,
            line_charge=mpfs.medicare_rate * random.uniform(0.9, 1.1),
            modifier_1="59" if random.random() < 0.3 else None,  # Possible modifier abuse
            place_of_service=claim.place_of_service,
            service_date=claim.statement_from_date,
        ))

        claim.scenario_type = FraudScenarioType.CODING_ISSUE
        claim.scenario_details["issue_type"] = "modifier" if claim.lines[0].modifier_1 else "diagnosis_link"

        return claim

    def create_near_duplicate(self, claim: ClaimData, existing_claims: list[dict]) -> ClaimData:
        """
        Create a claim similar to existing ones (same member/provider/date range).
        """
        # This will be handled during claim generation by tracking claim patterns
        return self._add_clean_lines(claim, scenario=FraudScenarioType.NEAR_DUPLICATE)

    # =====================================================
    # CLEAN CLAIMS (60%)
    # =====================================================

    def create_clean_claim(self, claim: ClaimData) -> ClaimData:
        """
        Create a properly coded, compliant claim.
        """
        return self._add_clean_lines(claim)

    def _add_clean_lines(
        self,
        claim: ClaimData,
        scenario: FraudScenarioType = FraudScenarioType.CLEAN,
    ) -> ClaimData:
        """Add clean service lines to a claim."""
        # Determine number of lines (1-4)
        num_lines = random.choices([1, 2, 3, 4], weights=[50, 30, 15, 5])[0]

        for i in range(num_lines):
            code, mpfs = self._select_clean_code()
            rate = mpfs.medicare_rate if mpfs else random.uniform(50, 300)

            # Bill at or slightly below Medicare rate
            charge = rate * random.uniform(0.85, 1.05)

            # Check MUE limit and stay under it
            mue_limit = self.ref.get_mue_limit(code)
            units = 1 if mue_limit is None or mue_limit <= 1 else random.randint(1, mue_limit)

            claim.lines.append(ClaimLine(
                line_number=i + 1,
                procedure_code=code,
                units=units,
                line_charge=charge * units,
                place_of_service=claim.place_of_service,
                service_date=claim.statement_from_date,
            ))

        claim.scenario_type = scenario
        return claim

    def _select_clean_code(self) -> tuple[str, Optional[MPFSEntry]]:
        """Select a procedure code that won't trigger fraud rules."""
        if self._priced_codes:
            code, mpfs = random.choice(self._priced_codes)
            return code, mpfs

        # Fallback to common E/M codes
        em_codes = ["99212", "99213", "99214", "99215", "99203", "99204", "99205"]
        code = random.choice(em_codes)
        return code, self.ref.mpfs.get(code)

    # =====================================================
    # SERVICE TYPE DISTRIBUTION
    # =====================================================

    def get_code_by_category(self, category: str) -> tuple[str, Optional[MPFSEntry]]:
        """Get a procedure code from a specific category."""
        codes = self.ref.get_codes_by_category(category)
        if codes:
            code = random.choice(codes)
            return code, self.ref.mpfs.get(code)
        return self._select_clean_code()

    # =====================================================
    # SCENARIO DISTRIBUTION
    # =====================================================

    def get_scenario_distribution(self, total_claims: int) -> dict[FraudScenarioType, int]:
        """
        Calculate the number of claims for each scenario type.

        Distribution:
        - 15% High-risk (1,500 for 10K claims)
        - 25% Medium-risk (2,500 for 10K claims)
        - 60% Clean (6,000 for 10K claims)
        """
        high_risk_count = int(total_claims * 0.15)
        medium_risk_count = int(total_claims * 0.25)
        clean_count = total_claims - high_risk_count - medium_risk_count

        # High-risk distribution
        oig_count = int(high_risk_count * 0.20)           # 300
        ptp_count = int(high_risk_count * 0.20)           # 300
        mue_count = int(high_risk_count * 0.20)           # 300
        fee_count = int(high_risk_count * 0.20)           # 300
        auth_count = int(high_risk_count * 0.13)          # ~200
        policy_count = high_risk_count - oig_count - ptp_count - mue_count - fee_count - auth_count  # ~100

        # Medium-risk distribution
        borderline_count = int(medium_risk_count * 0.32)  # 800
        near_mue_count = int(medium_risk_count * 0.24)    # 600
        coding_count = int(medium_risk_count * 0.20)      # 500
        near_dup_count = int(medium_risk_count * 0.16)    # 400
        volume_count = medium_risk_count - borderline_count - near_mue_count - coding_count - near_dup_count  # 200

        return {
            # High-risk
            FraudScenarioType.OIG_EXCLUDED: oig_count,
            FraudScenarioType.NCCI_PTP_VIOLATION: ptp_count,
            FraudScenarioType.NCCI_MUE_VIOLATION: mue_count,
            FraudScenarioType.FEE_SCHEDULE_OUTLIER: fee_count,
            FraudScenarioType.MISSING_AUTHORIZATION: auth_count,
            FraudScenarioType.POLICY_VIOLATION: policy_count,
            # Medium-risk
            FraudScenarioType.BORDERLINE_FEE: borderline_count,
            FraudScenarioType.NEAR_MUE_LIMIT: near_mue_count,
            FraudScenarioType.CODING_ISSUE: coding_count,
            FraudScenarioType.NEAR_DUPLICATE: near_dup_count,
            FraudScenarioType.VOLUME_SPIKE: volume_count,
            # Clean
            FraudScenarioType.CLEAN: clean_count,
        }

    @property
    def auth_required_codes(self) -> set[str]:
        """Get the set of authorization-required codes."""
        return self._auth_required_codes

    @property
    def oig_excluded_npis(self) -> list[str]:
        """Get the list of OIG excluded NPIs for provider generation."""
        return self._oig_npis
