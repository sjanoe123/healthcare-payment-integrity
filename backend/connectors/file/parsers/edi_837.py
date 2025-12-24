"""EDI 837 Parser for healthcare claims.

Parses ANSI X12 837 Professional (837P) and Institutional (837I)
claim files into structured claim records.

Segment Reference:
- ISA: Interchange Control Header
- GS: Functional Group Header
- ST: Transaction Set Header (837 start)
- BHT: Beginning of Hierarchical Transaction
- NM1: Name segment (patient, provider, subscriber)
- N3/N4: Address segments
- DMG: Demographic info
- CLM: Claim information
- SV1/SV2: Professional/Institutional service lines
- DTP: Date/time periods
- HI: Health care diagnosis information
- SE: Transaction Set Trailer
- GE: Functional Group Trailer
- IEA: Interchange Control Trailer
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator

logger = logging.getLogger(__name__)


@dataclass
class EDISegment:
    """Represents an EDI segment."""

    id: str
    elements: list[str]

    @classmethod
    def parse(cls, line: str, element_sep: str = "*") -> "EDISegment":
        """Parse a segment line."""
        parts = line.strip().split(element_sep)
        return cls(id=parts[0], elements=parts[1:] if len(parts) > 1 else [])

    def get(self, index: int, default: str = "") -> str:
        """Get element at index with default."""
        if 0 <= index < len(self.elements):
            return self.elements[index]
        return default


@dataclass
class ClaimRecord:
    """Parsed claim record from EDI 837."""

    # Claim identifiers
    claim_id: str = ""
    patient_control_number: str = ""
    claim_type: str = "837P"

    # Patient info
    patient_id: str = ""
    patient_first_name: str = ""
    patient_last_name: str = ""
    patient_dob: str = ""
    patient_gender: str = ""
    patient_address: str = ""
    patient_city: str = ""
    patient_state: str = ""
    patient_zip: str = ""

    # Subscriber info
    subscriber_id: str = ""
    subscriber_first_name: str = ""
    subscriber_last_name: str = ""
    subscriber_relationship: str = ""

    # Provider info
    billing_npi: str = ""
    billing_name: str = ""
    billing_taxonomy: str = ""
    rendering_npi: str = ""
    rendering_name: str = ""
    facility_npi: str = ""
    facility_name: str = ""

    # Claim details
    total_charge: float = 0.0
    place_of_service: str = ""
    frequency_code: str = ""
    admission_date: str = ""
    discharge_date: str = ""
    statement_from_date: str = ""
    statement_to_date: str = ""

    # Diagnosis codes
    diagnosis_codes: list[str] = field(default_factory=list)
    principal_diagnosis: str = ""

    # Service lines
    service_lines: list[dict[str, Any]] = field(default_factory=list)

    # Payer info
    payer_id: str = ""
    payer_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "claim_id": self.claim_id,
            "patient_control_number": self.patient_control_number,
            "claim_type": self.claim_type,
            "patient_id": self.patient_id,
            "patient_first_name": self.patient_first_name,
            "patient_last_name": self.patient_last_name,
            "patient_name": f"{self.patient_first_name} {self.patient_last_name}".strip(),
            "patient_dob": self.patient_dob,
            "patient_gender": self.patient_gender,
            "patient_address": self.patient_address,
            "patient_city": self.patient_city,
            "patient_state": self.patient_state,
            "patient_zip": self.patient_zip,
            "subscriber_id": self.subscriber_id,
            "subscriber_name": f"{self.subscriber_first_name} {self.subscriber_last_name}".strip(),
            "subscriber_relationship": self.subscriber_relationship,
            "billing_npi": self.billing_npi,
            "billing_name": self.billing_name,
            "billing_taxonomy": self.billing_taxonomy,
            "rendering_npi": self.rendering_npi,
            "rendering_name": self.rendering_name,
            "facility_npi": self.facility_npi,
            "facility_name": self.facility_name,
            "total_charge": self.total_charge,
            "place_of_service": self.place_of_service,
            "frequency_code": self.frequency_code,
            "admission_date": self.admission_date,
            "discharge_date": self.discharge_date,
            "statement_from_date": self.statement_from_date,
            "statement_to_date": self.statement_to_date,
            "diagnosis_codes": self.diagnosis_codes,
            "principal_diagnosis": self.principal_diagnosis,
            "service_lines": self.service_lines,
            "payer_id": self.payer_id,
            "payer_name": self.payer_name,
        }


class EDI837Parser:
    """Parser for EDI 837 Professional and Institutional claims.

    Handles both 837P (CMS-1500) and 837I (UB-04) formats with
    common segment parsing logic.
    """

    def __init__(
        self,
        element_separator: str = "*",
        segment_terminator: str = "~",
        subelement_separator: str = ":",
    ) -> None:
        """Initialize the parser.

        Args:
            element_separator: Character separating elements (default: *)
            segment_terminator: Character ending segments (default: ~)
            subelement_separator: Character separating sub-elements (default: :)
        """
        self.element_sep = element_separator
        self.segment_term = segment_terminator
        self.subelement_sep = subelement_separator

    def parse(
        self, file_path: str, limit: int | None = None
    ) -> Iterator[dict[str, Any]]:
        """Parse an EDI 837 file.

        Args:
            file_path: Path to EDI file
            limit: Optional limit on number of claims

        Yields:
            Claim dictionaries
        """
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Detect separators from ISA segment
        self._detect_separators(content)

        # Split into segments
        segments = self._split_segments(content)

        # Parse segments into claims
        claims_count = 0
        for claim in self._parse_segments(segments):
            yield claim.to_dict()
            claims_count += 1
            if limit and claims_count >= limit:
                break

    def _detect_separators(self, content: str) -> None:
        """Detect separators from ISA segment.

        The ISA segment is always exactly 106 characters with fixed positions
        for separator definitions.
        """
        # Find ISA segment
        isa_match = re.search(r"ISA.{103}", content)
        if isa_match:
            isa = isa_match.group(0)
            # Element separator is at position 3
            self.element_sep = isa[3]
            # Subelement separator is at position 104
            self.subelement_sep = isa[104]
            # Segment terminator is after the ISA segment
            if len(content) > isa_match.end():
                self.segment_term = content[isa_match.end()]

    def _split_segments(self, content: str) -> list[EDISegment]:
        """Split content into segment objects."""
        # Remove newlines and split by segment terminator
        content = content.replace("\n", "").replace("\r", "")
        lines = content.split(self.segment_term)

        segments = []
        for line in lines:
            line = line.strip()
            if line:
                segments.append(EDISegment.parse(line, self.element_sep))

        return segments

    def _parse_segments(self, segments: list[EDISegment]) -> Iterator[ClaimRecord]:
        """Parse segments into claim records.

        This implements a state machine to track hierarchical loops:
        - Loop 2000A: Billing Provider
        - Loop 2000B: Subscriber
        - Loop 2000C: Patient
        - Loop 2300: Claim
        - Loop 2400: Service Line
        """
        claim: ClaimRecord | None = None
        current_loop = ""
        service_line: dict[str, Any] = {}
        claim_type = "837P"  # Default to professional

        for segment in segments:
            seg_id = segment.id

            # Detect claim type from GS segment
            if seg_id == "GS":
                func_id = segment.get(0)
                if func_id == "HC":
                    claim_type = "837P"  # Health Care Claim
                elif func_id == "HI":
                    claim_type = "837I"  # Institutional

            # Transaction set header
            elif seg_id == "ST":
                trans_type = segment.get(0)
                if trans_type == "837":
                    # New transaction
                    pass

            # Hierarchical level
            elif seg_id == "HL":
                level_code = segment.get(2)
                if level_code == "20":
                    current_loop = "2000A"  # Billing Provider
                elif level_code == "22":
                    current_loop = "2000B"  # Subscriber
                elif level_code == "23":
                    current_loop = "2000C"  # Patient

            # Name segment
            elif seg_id == "NM1":
                entity_id = segment.get(0)
                self._parse_nm1(segment, entity_id, claim, current_loop)

            # Reference segment
            elif seg_id == "REF":
                ref_qual = segment.get(0)
                ref_value = segment.get(1)
                if claim:
                    if ref_qual == "EI":  # Employer ID
                        pass
                    elif ref_qual == "SY":  # SSN
                        pass
                    elif ref_qual == "1L":  # Member ID
                        claim.subscriber_id = ref_value

            # Demographics
            elif seg_id == "DMG":
                if claim and current_loop in ("2000B", "2000C"):
                    dob = segment.get(1)
                    gender = segment.get(2)
                    claim.patient_dob = self._parse_date(dob)
                    claim.patient_gender = {"M": "Male", "F": "Female"}.get(
                        gender, gender
                    )

            # Address
            elif seg_id == "N3":
                if claim and current_loop in ("2000B", "2000C"):
                    claim.patient_address = segment.get(0)

            elif seg_id == "N4":
                if claim and current_loop in ("2000B", "2000C"):
                    claim.patient_city = segment.get(0)
                    claim.patient_state = segment.get(1)
                    claim.patient_zip = segment.get(2)

            # Claim segment
            elif seg_id == "CLM":
                # Yield previous claim if exists
                if claim:
                    if service_line:
                        claim.service_lines.append(service_line)
                    yield claim

                # Start new claim
                claim = ClaimRecord()
                claim.claim_type = claim_type
                claim.patient_control_number = segment.get(0)
                claim.claim_id = segment.get(0)

                try:
                    claim.total_charge = float(segment.get(1, "0"))
                except ValueError:
                    claim.total_charge = 0.0

                # Facility code (element 5, subelement 0)
                facility_info = segment.get(4)
                if facility_info and self.subelement_sep in facility_info:
                    parts = facility_info.split(self.subelement_sep)
                    claim.place_of_service = parts[0] if parts else ""
                    claim.frequency_code = parts[1] if len(parts) > 1 else ""
                else:
                    claim.place_of_service = facility_info

                current_loop = "2300"
                service_line = {}

            # Health care diagnosis
            elif seg_id == "HI":
                if claim:
                    for i, element in enumerate(segment.elements):
                        if self.subelement_sep in element:
                            parts = element.split(self.subelement_sep)
                            diag_qual = parts[0] if parts else ""
                            diag_code = parts[1] if len(parts) > 1 else ""

                            if diag_code:
                                claim.diagnosis_codes.append(diag_code)
                                if diag_qual in ("ABK", "BK"):  # Principal diagnosis
                                    claim.principal_diagnosis = diag_code

            # Date/Time
            elif seg_id == "DTP":
                qual = segment.get(0)
                _fmt = segment.get(1)  # noqa: F841 - format code not used but kept for reference
                value = segment.get(2)

                if claim:
                    date_value = self._parse_date(value)
                    if qual == "435":  # Admission Date
                        claim.admission_date = date_value
                    elif qual == "096":  # Discharge Date
                        claim.discharge_date = date_value
                    elif qual == "434":  # Statement From
                        claim.statement_from_date = date_value
                    elif qual == "435":  # Statement To
                        claim.statement_to_date = date_value
                    elif qual == "472" and current_loop == "2400":  # Service Date
                        if "-" in value:  # Date range
                            dates = value.split("-")
                            service_line["service_from_date"] = self._parse_date(
                                dates[0]
                            )
                            service_line["service_to_date"] = self._parse_date(
                                dates[1] if len(dates) > 1 else dates[0]
                            )
                        else:
                            service_line["service_date"] = date_value

            # Service line (Professional)
            elif seg_id == "SV1":
                if claim:
                    if service_line:
                        claim.service_lines.append(service_line)

                    service_line = {}
                    current_loop = "2400"

                    # Procedure code (element 0, compound)
                    proc_info = segment.get(0)
                    if self.subelement_sep in proc_info:
                        parts = proc_info.split(self.subelement_sep)
                        service_line["procedure_code"] = (
                            parts[1] if len(parts) > 1 else ""
                        )
                        service_line["modifier_1"] = parts[2] if len(parts) > 2 else ""
                        service_line["modifier_2"] = parts[3] if len(parts) > 3 else ""
                        service_line["modifier_3"] = parts[4] if len(parts) > 4 else ""
                        service_line["modifier_4"] = parts[5] if len(parts) > 5 else ""
                    else:
                        service_line["procedure_code"] = proc_info

                    try:
                        service_line["charge_amount"] = float(segment.get(1, "0"))
                    except ValueError:
                        service_line["charge_amount"] = 0.0

                    service_line["units"] = segment.get(3, "1")
                    service_line["place_of_service"] = segment.get(4, "")

                    # Diagnosis pointer
                    diag_pointer = segment.get(6)
                    if diag_pointer:
                        pointers = diag_pointer.split(self.subelement_sep)
                        service_line["diagnosis_pointers"] = pointers

            # Service line (Institutional)
            elif seg_id == "SV2":
                if claim:
                    if service_line:
                        claim.service_lines.append(service_line)

                    service_line = {}
                    current_loop = "2400"

                    service_line["revenue_code"] = segment.get(0)

                    # Procedure code
                    proc_info = segment.get(1)
                    if self.subelement_sep in proc_info:
                        parts = proc_info.split(self.subelement_sep)
                        service_line["procedure_code"] = (
                            parts[1] if len(parts) > 1 else ""
                        )
                    else:
                        service_line["procedure_code"] = proc_info

                    try:
                        service_line["charge_amount"] = float(segment.get(2, "0"))
                    except ValueError:
                        service_line["charge_amount"] = 0.0

                    service_line["units"] = segment.get(4, "1")

            # Line item reference
            elif seg_id == "REF" and current_loop == "2400":
                ref_qual = segment.get(0)
                ref_value = segment.get(1)
                if ref_qual == "6R":  # Line Item Control Number
                    service_line["line_item_control_number"] = ref_value

            # Transaction trailer
            elif seg_id == "SE":
                # End of transaction - yield final claim
                if claim:
                    if service_line:
                        claim.service_lines.append(service_line)
                    yield claim
                    claim = None
                    service_line = {}

    def _parse_nm1(
        self,
        segment: EDISegment,
        entity_id: str,
        claim: ClaimRecord | None,
        loop: str,
    ) -> None:
        """Parse NM1 (Name) segment.

        Args:
            segment: The NM1 segment
            entity_id: Entity identifier code
            claim: Current claim record
            loop: Current loop context
        """
        entity_type = segment.get(1)
        last_name = segment.get(2)
        first_name = segment.get(3)
        _middle_name = segment.get(4)  # noqa: F841 - captured but not used in output
        id_qual = segment.get(7)
        id_value = segment.get(8)

        if entity_type == "1":  # Person
            name = f"{first_name} {last_name}".strip()
        else:  # Organization
            name = last_name

        if not claim:
            return

        # Billing provider
        if entity_id == "85":
            claim.billing_name = name
            if id_qual == "XX":  # NPI
                claim.billing_npi = id_value

        # Rendering provider
        elif entity_id == "82":
            claim.rendering_name = name
            if id_qual == "XX":
                claim.rendering_npi = id_value

        # Service facility
        elif entity_id == "77":
            claim.facility_name = name
            if id_qual == "XX":
                claim.facility_npi = id_value

        # Subscriber
        elif entity_id == "IL":
            claim.subscriber_first_name = first_name
            claim.subscriber_last_name = last_name
            if id_qual == "MI":  # Member ID
                claim.subscriber_id = id_value

        # Patient
        elif entity_id == "QC":
            claim.patient_first_name = first_name
            claim.patient_last_name = last_name
            claim.patient_id = id_value

        # Payer
        elif entity_id == "PR":
            claim.payer_name = name
            claim.payer_id = id_value

    def _parse_date(self, date_str: str) -> str:
        """Parse EDI date format (CCYYMMDD) to ISO format.

        Args:
            date_str: Date in CCYYMMDD format

        Returns:
            Date in YYYY-MM-DD format or original if parsing fails
        """
        if not date_str or len(date_str) < 8:
            return date_str

        try:
            dt = datetime.strptime(date_str[:8], "%Y%m%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return date_str
