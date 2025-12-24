"""Claims data type interface.

Defines structured schemas for healthcare claims (837P/837I) with
validation and normalization to OMOP CDM compatible format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class ClaimType(str, Enum):
    """Type of healthcare claim."""

    PROFESSIONAL = "837P"  # CMS-1500 equivalent
    INSTITUTIONAL = "837I"  # UB-04 equivalent
    DENTAL = "837D"
    PHARMACY = "NCPDP"


class ClaimStatus(str, Enum):
    """Claim processing status."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PAID = "paid"
    DENIED = "denied"


@dataclass
class ClaimLine:
    """Individual service line on a claim."""

    line_number: int
    procedure_code: str
    procedure_code_type: str = "CPT"  # CPT, HCPCS, ICD10PCS
    modifier_1: str | None = None
    modifier_2: str | None = None
    modifier_3: str | None = None
    modifier_4: str | None = None
    diagnosis_pointer: list[int] = field(default_factory=list)
    service_date: date | None = None
    service_date_end: date | None = None
    place_of_service: str | None = None
    units: Decimal = Decimal("1")
    unit_type: str = "UN"  # UN=units, MJ=minutes, etc.
    charge_amount: Decimal = Decimal("0")
    allowed_amount: Decimal | None = None
    paid_amount: Decimal | None = None
    revenue_code: str | None = None  # For institutional claims
    ndc_code: str | None = None  # For drugs
    rendering_provider_npi: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "line_number": self.line_number,
            "procedure_code": self.procedure_code,
            "procedure_code_type": self.procedure_code_type,
            "modifier_1": self.modifier_1,
            "modifier_2": self.modifier_2,
            "modifier_3": self.modifier_3,
            "modifier_4": self.modifier_4,
            "diagnosis_pointer": self.diagnosis_pointer,
            "service_date": self.service_date.isoformat()
            if self.service_date
            else None,
            "service_date_end": (
                self.service_date_end.isoformat() if self.service_date_end else None
            ),
            "place_of_service": self.place_of_service,
            "units": float(self.units),
            "unit_type": self.unit_type,
            "charge_amount": float(self.charge_amount),
            "allowed_amount": float(self.allowed_amount)
            if self.allowed_amount
            else None,
            "paid_amount": float(self.paid_amount) if self.paid_amount else None,
            "revenue_code": self.revenue_code,
            "ndc_code": self.ndc_code,
            "rendering_provider_npi": self.rendering_provider_npi,
        }


@dataclass
class ClaimRecord:
    """Complete healthcare claim record."""

    # Identifiers
    claim_id: str
    claim_type: ClaimType
    patient_control_number: str | None = None

    # Patient info
    member_id: str | None = None
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    patient_dob: date | None = None
    patient_gender: str | None = None  # M, F, U

    # Provider info
    billing_provider_npi: str | None = None
    billing_provider_name: str | None = None
    billing_provider_taxonomy: str | None = None
    rendering_provider_npi: str | None = None
    rendering_provider_name: str | None = None
    referring_provider_npi: str | None = None
    facility_npi: str | None = None
    facility_name: str | None = None

    # Payer info
    payer_id: str | None = None
    payer_name: str | None = None
    subscriber_id: str | None = None
    group_number: str | None = None

    # Dates
    statement_from_date: date | None = None
    statement_to_date: date | None = None
    admission_date: date | None = None
    discharge_date: date | None = None

    # Diagnosis codes
    principal_diagnosis: str | None = None
    diagnosis_codes: list[str] = field(default_factory=list)
    diagnosis_code_type: str = "ICD10"  # ICD10, ICD9

    # Institutional fields
    admission_type: str | None = None
    admission_source: str | None = None
    discharge_status: str | None = None
    drg_code: str | None = None
    bill_type: str | None = None  # e.g., "0111" for inpatient

    # Financial
    total_charge: Decimal = Decimal("0")
    total_allowed: Decimal | None = None
    total_paid: Decimal | None = None

    # Service lines
    lines: list[ClaimLine] = field(default_factory=list)

    # Metadata
    status: ClaimStatus = ClaimStatus.PENDING
    source_file: str | None = None
    received_date: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "claim_id": self.claim_id,
            "claim_type": self.claim_type.value,
            "patient_control_number": self.patient_control_number,
            "member_id": self.member_id,
            "patient_first_name": self.patient_first_name,
            "patient_last_name": self.patient_last_name,
            "patient_dob": self.patient_dob.isoformat() if self.patient_dob else None,
            "patient_gender": self.patient_gender,
            "billing_provider_npi": self.billing_provider_npi,
            "billing_provider_name": self.billing_provider_name,
            "billing_provider_taxonomy": self.billing_provider_taxonomy,
            "rendering_provider_npi": self.rendering_provider_npi,
            "rendering_provider_name": self.rendering_provider_name,
            "referring_provider_npi": self.referring_provider_npi,
            "facility_npi": self.facility_npi,
            "facility_name": self.facility_name,
            "payer_id": self.payer_id,
            "payer_name": self.payer_name,
            "subscriber_id": self.subscriber_id,
            "group_number": self.group_number,
            "statement_from_date": (
                self.statement_from_date.isoformat()
                if self.statement_from_date
                else None
            ),
            "statement_to_date": (
                self.statement_to_date.isoformat() if self.statement_to_date else None
            ),
            "admission_date": (
                self.admission_date.isoformat() if self.admission_date else None
            ),
            "discharge_date": (
                self.discharge_date.isoformat() if self.discharge_date else None
            ),
            "principal_diagnosis": self.principal_diagnosis,
            "diagnosis_codes": self.diagnosis_codes,
            "diagnosis_code_type": self.diagnosis_code_type,
            "admission_type": self.admission_type,
            "admission_source": self.admission_source,
            "discharge_status": self.discharge_status,
            "drg_code": self.drg_code,
            "bill_type": self.bill_type,
            "total_charge": float(self.total_charge),
            "total_allowed": float(self.total_allowed) if self.total_allowed else None,
            "total_paid": float(self.total_paid) if self.total_paid else None,
            "lines": [line.to_dict() for line in self.lines],
            "status": self.status.value,
            "source_file": self.source_file,
            "received_date": (
                self.received_date.isoformat() if self.received_date else None
            ),
        }


@dataclass
class ClaimValidationResult:
    """Result of claim validation."""

    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)


def validate_claim(claim: ClaimRecord) -> ClaimValidationResult:
    """Validate a claim record.

    Checks for:
    - Required fields
    - Valid NPI format
    - Valid diagnosis code format
    - Valid procedure code format
    - Date logic (service dates, admission/discharge)
    - Financial consistency

    Args:
        claim: ClaimRecord to validate

    Returns:
        ClaimValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    # Required fields
    if not claim.claim_id:
        errors.append({"field": "claim_id", "message": "Claim ID is required"})

    if not claim.member_id:
        errors.append({"field": "member_id", "message": "Member ID is required"})

    if not claim.billing_provider_npi:
        errors.append(
            {
                "field": "billing_provider_npi",
                "message": "Billing provider NPI is required",
            }
        )

    # NPI validation (10-digit number)
    npi_pattern = re.compile(r"^\d{10}$")

    if claim.billing_provider_npi and not npi_pattern.match(claim.billing_provider_npi):
        errors.append(
            {
                "field": "billing_provider_npi",
                "message": f"Invalid NPI format: {claim.billing_provider_npi}",
            }
        )

    if claim.rendering_provider_npi and not npi_pattern.match(
        claim.rendering_provider_npi
    ):
        errors.append(
            {
                "field": "rendering_provider_npi",
                "message": f"Invalid NPI format: {claim.rendering_provider_npi}",
            }
        )

    # Diagnosis code validation
    icd10_pattern = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")
    icd9_pattern = re.compile(r"^\d{3}(\.\d{1,2})?$")

    for i, dx in enumerate(claim.diagnosis_codes):
        if claim.diagnosis_code_type == "ICD10":
            if not icd10_pattern.match(dx):
                errors.append(
                    {
                        "field": f"diagnosis_codes[{i}]",
                        "message": f"Invalid ICD-10 code format: {dx}",
                    }
                )
        elif claim.diagnosis_code_type == "ICD9":
            if not icd9_pattern.match(dx):
                errors.append(
                    {
                        "field": f"diagnosis_codes[{i}]",
                        "message": f"Invalid ICD-9 code format: {dx}",
                    }
                )

    # Principal diagnosis should be in diagnosis list
    if (
        claim.principal_diagnosis
        and claim.principal_diagnosis not in claim.diagnosis_codes
    ):
        warnings.append(
            {
                "field": "principal_diagnosis",
                "message": "Principal diagnosis not in diagnosis codes list",
            }
        )

    # Service line validation
    if not claim.lines:
        errors.append(
            {"field": "lines", "message": "At least one service line is required"}
        )

    for i, line in enumerate(claim.lines):
        # Procedure code format
        cpt_pattern = re.compile(r"^\d{5}$")
        hcpcs_pattern = re.compile(r"^[A-Z]\d{4}$")

        if line.procedure_code_type in ("CPT", "HCPCS"):
            if not (
                cpt_pattern.match(line.procedure_code)
                or hcpcs_pattern.match(line.procedure_code)
            ):
                errors.append(
                    {
                        "field": f"lines[{i}].procedure_code",
                        "message": f"Invalid procedure code format: {line.procedure_code}",
                    }
                )

        # Charge amount
        if line.charge_amount <= 0:
            warnings.append(
                {
                    "field": f"lines[{i}].charge_amount",
                    "message": "Charge amount should be positive",
                }
            )

        # Units
        if line.units <= 0:
            errors.append(
                {
                    "field": f"lines[{i}].units",
                    "message": "Units must be positive",
                }
            )

        # Diagnosis pointer validation
        for ptr in line.diagnosis_pointer:
            if ptr < 1 or ptr > len(claim.diagnosis_codes):
                errors.append(
                    {
                        "field": f"lines[{i}].diagnosis_pointer",
                        "message": f"Invalid diagnosis pointer: {ptr}",
                    }
                )

    # Date validation
    if claim.statement_from_date and claim.statement_to_date:
        if claim.statement_from_date > claim.statement_to_date:
            errors.append(
                {
                    "field": "statement_dates",
                    "message": "Statement from date cannot be after to date",
                }
            )

    if claim.admission_date and claim.discharge_date:
        if claim.admission_date > claim.discharge_date:
            errors.append(
                {
                    "field": "admission_dates",
                    "message": "Admission date cannot be after discharge date",
                }
            )

    # Institutional claim requirements
    if claim.claim_type == ClaimType.INSTITUTIONAL:
        if not claim.bill_type:
            warnings.append(
                {
                    "field": "bill_type",
                    "message": "Bill type is recommended for institutional claims",
                }
            )

        for i, line in enumerate(claim.lines):
            if not line.revenue_code:
                warnings.append(
                    {
                        "field": f"lines[{i}].revenue_code",
                        "message": "Revenue code is recommended for institutional claims",
                    }
                )

    # Financial consistency
    calculated_total = sum(line.charge_amount for line in claim.lines)
    if abs(float(claim.total_charge) - float(calculated_total)) > 0.01:
        warnings.append(
            {
                "field": "total_charge",
                "message": f"Total charge ({claim.total_charge}) doesn't match sum of lines ({calculated_total})",
            }
        )

    return ClaimValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def normalize_claim(data: dict[str, Any]) -> ClaimRecord:
    """Normalize raw claim data to ClaimRecord.

    Handles various input formats and field name variations.

    Args:
        data: Raw claim dictionary

    Returns:
        Normalized ClaimRecord
    """

    # Parse dates
    def parse_date(val: Any) -> date | None:
        if val is None:
            return None
        if isinstance(val, date):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            # Try common formats
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d", "%m-%d-%Y"):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
        return None

    # Parse decimal
    def parse_decimal(val: Any) -> Decimal:
        if val is None:
            return Decimal("0")
        try:
            return Decimal(str(val))
        except Exception:
            return Decimal("0")

    # Determine claim type
    claim_type_str = data.get("claim_type", data.get("type", "837P"))
    try:
        claim_type = ClaimType(claim_type_str)
    except ValueError:
        claim_type = ClaimType.PROFESSIONAL

    # Parse service lines
    lines = []
    raw_lines = data.get("lines", data.get("service_lines", data.get("items", [])))
    for i, line_data in enumerate(raw_lines):
        if isinstance(line_data, dict):
            lines.append(
                ClaimLine(
                    line_number=line_data.get("line_number", i + 1),
                    procedure_code=line_data.get(
                        "procedure_code", line_data.get("cpt_code", "")
                    ),
                    procedure_code_type=line_data.get("procedure_code_type", "CPT"),
                    modifier_1=line_data.get("modifier_1", line_data.get("modifier1")),
                    modifier_2=line_data.get("modifier_2", line_data.get("modifier2")),
                    modifier_3=line_data.get("modifier_3", line_data.get("modifier3")),
                    modifier_4=line_data.get("modifier_4", line_data.get("modifier4")),
                    diagnosis_pointer=line_data.get(
                        "diagnosis_pointer", line_data.get("dx_pointer", [])
                    ),
                    service_date=parse_date(
                        line_data.get("service_date", line_data.get("dos"))
                    ),
                    service_date_end=parse_date(line_data.get("service_date_end")),
                    place_of_service=line_data.get(
                        "place_of_service", line_data.get("pos")
                    ),
                    units=parse_decimal(
                        line_data.get("units", line_data.get("qty", 1))
                    ),
                    unit_type=line_data.get("unit_type", "UN"),
                    charge_amount=parse_decimal(
                        line_data.get("charge_amount", line_data.get("charge", 0))
                    ),
                    allowed_amount=parse_decimal(line_data.get("allowed_amount"))
                    if line_data.get("allowed_amount")
                    else None,
                    paid_amount=parse_decimal(line_data.get("paid_amount"))
                    if line_data.get("paid_amount")
                    else None,
                    revenue_code=line_data.get("revenue_code"),
                    ndc_code=line_data.get("ndc_code", line_data.get("ndc")),
                    rendering_provider_npi=line_data.get("rendering_provider_npi"),
                )
            )

    return ClaimRecord(
        claim_id=data.get("claim_id", data.get("id", "")),
        claim_type=claim_type,
        patient_control_number=data.get(
            "patient_control_number", data.get("pcn", data.get("control_number"))
        ),
        member_id=data.get("member_id", data.get("subscriber_id")),
        patient_first_name=data.get(
            "patient_first_name", data.get("first_name", data.get("fname"))
        ),
        patient_last_name=data.get(
            "patient_last_name", data.get("last_name", data.get("lname"))
        ),
        patient_dob=parse_date(data.get("patient_dob", data.get("dob"))),
        patient_gender=data.get("patient_gender", data.get("gender")),
        billing_provider_npi=data.get(
            "billing_provider_npi", data.get("billing_npi", data.get("provider_npi"))
        ),
        billing_provider_name=data.get(
            "billing_provider_name", data.get("provider_name")
        ),
        billing_provider_taxonomy=data.get("billing_provider_taxonomy"),
        rendering_provider_npi=data.get("rendering_provider_npi"),
        rendering_provider_name=data.get("rendering_provider_name"),
        referring_provider_npi=data.get("referring_provider_npi"),
        facility_npi=data.get("facility_npi"),
        facility_name=data.get("facility_name"),
        payer_id=data.get("payer_id"),
        payer_name=data.get("payer_name"),
        subscriber_id=data.get("subscriber_id"),
        group_number=data.get("group_number"),
        statement_from_date=parse_date(data.get("statement_from_date")),
        statement_to_date=parse_date(data.get("statement_to_date")),
        admission_date=parse_date(data.get("admission_date")),
        discharge_date=parse_date(data.get("discharge_date")),
        principal_diagnosis=data.get(
            "principal_diagnosis", data.get("primary_diagnosis")
        ),
        diagnosis_codes=data.get(
            "diagnosis_codes", data.get("diagnoses", data.get("dx_codes", []))
        ),
        diagnosis_code_type=data.get("diagnosis_code_type", "ICD10"),
        admission_type=data.get("admission_type"),
        admission_source=data.get("admission_source"),
        discharge_status=data.get("discharge_status"),
        drg_code=data.get("drg_code", data.get("drg")),
        bill_type=data.get("bill_type"),
        total_charge=parse_decimal(
            data.get("total_charge", data.get("total_amount", 0))
        ),
        total_allowed=parse_decimal(data.get("total_allowed"))
        if data.get("total_allowed")
        else None,
        total_paid=parse_decimal(data.get("total_paid"))
        if data.get("total_paid")
        else None,
        lines=lines,
        source_file=data.get("source_file", data.get("_source_file")),
        received_date=datetime.now(),
    )
