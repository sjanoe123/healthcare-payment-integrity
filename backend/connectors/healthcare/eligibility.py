"""Eligibility data type interface.

Defines structured schemas for healthcare eligibility data (270/271)
with validation and normalization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


class EligibilityStatus(str):
    """Member eligibility status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    TERMINATED = "terminated"


@dataclass
class BenefitInfo:
    """Information about a specific benefit."""

    benefit_type: str  # health, dental, vision, pharmacy
    coverage_level: str  # individual, family, employee_only
    in_network: bool = True
    copay_amount: float | None = None
    coinsurance_percent: float | None = None
    deductible_amount: float | None = None
    deductible_remaining: float | None = None
    out_of_pocket_max: float | None = None
    out_of_pocket_remaining: float | None = None
    benefit_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "benefit_type": self.benefit_type,
            "coverage_level": self.coverage_level,
            "in_network": self.in_network,
            "copay_amount": self.copay_amount,
            "coinsurance_percent": self.coinsurance_percent,
            "deductible_amount": self.deductible_amount,
            "deductible_remaining": self.deductible_remaining,
            "out_of_pocket_max": self.out_of_pocket_max,
            "out_of_pocket_remaining": self.out_of_pocket_remaining,
            "benefit_notes": self.benefit_notes,
        }


@dataclass
class CoverageInfo:
    """Coverage period information."""

    coverage_type: str  # primary, secondary, tertiary
    plan_name: str | None = None
    plan_id: str | None = None
    group_number: str | None = None
    group_name: str | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    payer_id: str | None = None
    payer_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "coverage_type": self.coverage_type,
            "plan_name": self.plan_name,
            "plan_id": self.plan_id,
            "group_number": self.group_number,
            "group_name": self.group_name,
            "effective_date": (
                self.effective_date.isoformat() if self.effective_date else None
            ),
            "termination_date": (
                self.termination_date.isoformat() if self.termination_date else None
            ),
            "payer_id": self.payer_id,
            "payer_name": self.payer_name,
        }


@dataclass
class EligibilityRecord:
    """Complete eligibility record for a member."""

    # Identifiers
    member_id: str
    subscriber_id: str | None = None

    # Member demographics
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None  # M, F, U
    ssn_last_four: str | None = None

    # Contact info
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    email: str | None = None

    # Eligibility status
    status: str = EligibilityStatus.ACTIVE
    status_date: date | None = None

    # Coverage information
    coverages: list[CoverageInfo] = field(default_factory=list)

    # Benefits
    benefits: list[BenefitInfo] = field(default_factory=list)

    # Primary care
    pcp_npi: str | None = None
    pcp_name: str | None = None
    pcp_effective_date: date | None = None

    # Coordination of benefits
    cob_order: int = 1  # 1=primary, 2=secondary, etc.
    other_insurance: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    source_system: str | None = None
    last_verified: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "member_id": self.member_id,
            "subscriber_id": self.subscriber_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "middle_name": self.middle_name,
            "date_of_birth": (
                self.date_of_birth.isoformat() if self.date_of_birth else None
            ),
            "gender": self.gender,
            "ssn_last_four": self.ssn_last_four,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "phone": self.phone,
            "email": self.email,
            "status": self.status,
            "status_date": self.status_date.isoformat() if self.status_date else None,
            "coverages": [c.to_dict() for c in self.coverages],
            "benefits": [b.to_dict() for b in self.benefits],
            "pcp_npi": self.pcp_npi,
            "pcp_name": self.pcp_name,
            "pcp_effective_date": (
                self.pcp_effective_date.isoformat() if self.pcp_effective_date else None
            ),
            "cob_order": self.cob_order,
            "other_insurance": self.other_insurance,
            "source_system": self.source_system,
            "last_verified": (
                self.last_verified.isoformat() if self.last_verified else None
            ),
        }

    def is_active_on(self, check_date: date) -> bool:
        """Check if member has active coverage on a specific date.

        Args:
            check_date: Date to check eligibility

        Returns:
            True if member has active coverage on that date
        """
        if self.status != EligibilityStatus.ACTIVE:
            return False

        for coverage in self.coverages:
            if coverage.effective_date and coverage.effective_date > check_date:
                continue
            if coverage.termination_date and coverage.termination_date < check_date:
                continue
            return True

        return False


@dataclass
class EligibilityValidationResult:
    """Result of eligibility validation."""

    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)


def validate_eligibility(record: EligibilityRecord) -> EligibilityValidationResult:
    """Validate an eligibility record.

    Checks for:
    - Required fields
    - Valid date formats and logic
    - Valid state codes
    - Valid phone/email formats

    Args:
        record: EligibilityRecord to validate

    Returns:
        EligibilityValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    # Required fields
    if not record.member_id:
        errors.append({"field": "member_id", "message": "Member ID is required"})

    # Name validation
    if not record.first_name and not record.last_name:
        warnings.append(
            {
                "field": "name",
                "message": "Member name is recommended",
            }
        )

    # Date of birth
    if record.date_of_birth:
        if record.date_of_birth > date.today():
            errors.append(
                {
                    "field": "date_of_birth",
                    "message": "Date of birth cannot be in the future",
                }
            )

    # State code validation
    valid_states = {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
        "PR",
        "VI",
        "GU",
        "AS",
        "MP",
    }

    if record.state and record.state.upper() not in valid_states:
        warnings.append(
            {
                "field": "state",
                "message": f"Invalid state code: {record.state}",
            }
        )

    # Zip code validation
    if record.zip_code:
        zip_pattern = re.compile(r"^\d{5}(-\d{4})?$")
        if not zip_pattern.match(record.zip_code):
            warnings.append(
                {
                    "field": "zip_code",
                    "message": f"Invalid zip code format: {record.zip_code}",
                }
            )

    # Phone validation
    if record.phone:
        phone_digits = re.sub(r"\D", "", record.phone)
        if len(phone_digits) != 10:
            warnings.append(
                {
                    "field": "phone",
                    "message": f"Invalid phone number: {record.phone}",
                }
            )

    # Email validation
    if record.email:
        email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        if not email_pattern.match(record.email):
            warnings.append(
                {
                    "field": "email",
                    "message": f"Invalid email format: {record.email}",
                }
            )

    # Coverage validation
    if not record.coverages:
        warnings.append(
            {
                "field": "coverages",
                "message": "No coverage information provided",
            }
        )

    for i, coverage in enumerate(record.coverages):
        if coverage.effective_date and coverage.termination_date:
            if coverage.effective_date > coverage.termination_date:
                errors.append(
                    {
                        "field": f"coverages[{i}]",
                        "message": "Effective date cannot be after termination date",
                    }
                )

    # PCP NPI validation
    if record.pcp_npi:
        npi_pattern = re.compile(r"^\d{10}$")
        if not npi_pattern.match(record.pcp_npi):
            errors.append(
                {
                    "field": "pcp_npi",
                    "message": f"Invalid NPI format: {record.pcp_npi}",
                }
            )

    return EligibilityValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def normalize_eligibility(data: dict[str, Any]) -> EligibilityRecord:
    """Normalize raw eligibility data to EligibilityRecord.

    Handles various input formats and field name variations.

    Args:
        data: Raw eligibility dictionary

    Returns:
        Normalized EligibilityRecord
    """

    def parse_date(val: Any) -> date | None:
        if val is None:
            return None
        if isinstance(val, date):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d", "%m-%d-%Y"):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
        return None

    # Parse coverages
    coverages = []
    raw_coverages = data.get("coverages", data.get("coverage", []))
    if isinstance(raw_coverages, dict):
        raw_coverages = [raw_coverages]
    for cov in raw_coverages:
        if isinstance(cov, dict):
            coverages.append(
                CoverageInfo(
                    coverage_type=cov.get("coverage_type", "primary"),
                    plan_name=cov.get("plan_name"),
                    plan_id=cov.get("plan_id"),
                    group_number=cov.get("group_number"),
                    group_name=cov.get("group_name"),
                    effective_date=parse_date(cov.get("effective_date")),
                    termination_date=parse_date(cov.get("termination_date")),
                    payer_id=cov.get("payer_id"),
                    payer_name=cov.get("payer_name"),
                )
            )

    # If no coverages but has top-level coverage fields
    if not coverages and data.get("effective_date"):
        coverages.append(
            CoverageInfo(
                coverage_type="primary",
                plan_name=data.get("plan_name"),
                plan_id=data.get("plan_id"),
                group_number=data.get("group_number"),
                group_name=data.get("group_name"),
                effective_date=parse_date(data.get("effective_date")),
                termination_date=parse_date(data.get("termination_date")),
                payer_id=data.get("payer_id"),
                payer_name=data.get("payer_name"),
            )
        )

    # Parse benefits
    benefits = []
    raw_benefits = data.get("benefits", [])
    for ben in raw_benefits:
        if isinstance(ben, dict):
            benefits.append(
                BenefitInfo(
                    benefit_type=ben.get("benefit_type", "health"),
                    coverage_level=ben.get("coverage_level", "individual"),
                    in_network=ben.get("in_network", True),
                    copay_amount=ben.get("copay_amount"),
                    coinsurance_percent=ben.get("coinsurance_percent"),
                    deductible_amount=ben.get("deductible_amount"),
                    deductible_remaining=ben.get("deductible_remaining"),
                    out_of_pocket_max=ben.get("out_of_pocket_max"),
                    out_of_pocket_remaining=ben.get("out_of_pocket_remaining"),
                    benefit_notes=ben.get("benefit_notes"),
                )
            )

    return EligibilityRecord(
        member_id=data.get("member_id", data.get("id", "")),
        subscriber_id=data.get("subscriber_id"),
        first_name=data.get("first_name", data.get("fname")),
        last_name=data.get("last_name", data.get("lname")),
        middle_name=data.get("middle_name", data.get("mname")),
        date_of_birth=parse_date(data.get("date_of_birth", data.get("dob"))),
        gender=data.get("gender", data.get("sex")),
        ssn_last_four=data.get("ssn_last_four"),
        address_line1=data.get("address_line1", data.get("address1")),
        address_line2=data.get("address_line2", data.get("address2")),
        city=data.get("city"),
        state=data.get("state"),
        zip_code=data.get("zip_code", data.get("zip")),
        phone=data.get("phone", data.get("phone_number")),
        email=data.get("email"),
        status=data.get("status", EligibilityStatus.ACTIVE),
        status_date=parse_date(data.get("status_date")),
        coverages=coverages,
        benefits=benefits,
        pcp_npi=data.get("pcp_npi"),
        pcp_name=data.get("pcp_name"),
        pcp_effective_date=parse_date(data.get("pcp_effective_date")),
        cob_order=data.get("cob_order", 1),
        other_insurance=data.get("other_insurance", []),
        source_system=data.get("source_system", data.get("_source_file")),
        last_verified=datetime.now(),
    )
