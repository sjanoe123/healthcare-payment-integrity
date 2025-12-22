"""OMOP CDM schema subset for healthcare claims.

This module defines the canonical OMOP CDM fields relevant to payment integrity,
with built-in aliases for common field naming conventions across different
data sources (EDI 837, CSV uploads, payer formats).

Based on OMOP CDM v5.4:
- https://ohdsi.github.io/CommonDataModel/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FieldType = Literal["str", "int", "float", "date", "list[str]"]


@dataclass
class OMOPField:
    """Definition of an OMOP CDM field with mapping aliases."""

    omop_field: str
    field_type: FieldType
    required: bool = False
    aliases: list[str] = field(default_factory=list)
    description: str = ""


# OMOP CDM claim-relevant fields organized by OMOP table
# Reference: https://ohdsi.github.io/CommonDataModel/cdm54.html

VISIT_OCCURRENCE_FIELDS = {
    "visit_occurrence_id": OMOPField(
        omop_field="visit_occurrence_id",
        field_type="str",
        required=True,
        aliases=["claim_id", "encounter_id", "visit_id"],
        description="Unique identifier for each visit/claim",
    ),
    "person_id": OMOPField(
        omop_field="person_id",
        field_type="str",
        required=True,
        aliases=[
            "member_id",
            "patient_id",
            "subscriber_id",
            "patient_control_number",
            "MemberID",
            "PatientID",
        ],
        description="Unique identifier for the patient/member",
    ),
    "visit_start_date": OMOPField(
        omop_field="visit_start_date",
        field_type="date",
        required=True,
        aliases=[
            "service_date",
            "date_of_service",
            "dos",
            "statement_from_date",
            "ServiceDate",
            "DateOfService",
        ],
        description="Start date of the visit/service",
    ),
    "visit_end_date": OMOPField(
        omop_field="visit_end_date",
        field_type="date",
        required=False,
        aliases=[
            "service_end_date",
            "statement_to_date",
            "discharge_date",
        ],
        description="End date of the visit/service",
    ),
    "visit_type_concept_id": OMOPField(
        omop_field="visit_type_concept_id",
        field_type="int",
        required=False,
        aliases=[],
        description="Type of visit (inpatient, outpatient, etc.)",
    ),
    "care_site_id": OMOPField(
        omop_field="care_site_id",
        field_type="str",
        required=False,
        aliases=["facility_id", "service_facility_npi", "facility_npi"],
        description="Care site where service was rendered",
    ),
    "visit_source_value": OMOPField(
        omop_field="visit_source_value",
        field_type="str",
        required=False,
        aliases=["claim_type", "claim_form_type", "bill_type"],
        description="Source value for visit type",
    ),
}

PROCEDURE_OCCURRENCE_FIELDS = {
    "procedure_occurrence_id": OMOPField(
        omop_field="procedure_occurrence_id",
        field_type="str",
        required=False,
        aliases=["line_id", "service_line_id", "claim_line_number"],
        description="Unique identifier for procedure line",
    ),
    "procedure_concept_id": OMOPField(
        omop_field="procedure_concept_id",
        field_type="int",
        required=False,
        aliases=[],
        description="OMOP standard concept ID for procedure",
    ),
    "procedure_source_value": OMOPField(
        omop_field="procedure_source_value",
        field_type="str",
        required=True,
        aliases=[
            "procedure_code",
            "cpt_code",
            "hcpcs_code",
            "service_code",
            "CPTCode",
            "HCPCS",
            "ProcedureCode",
        ],
        description="Source procedure code (CPT/HCPCS)",
    ),
    "procedure_date": OMOPField(
        omop_field="procedure_date",
        field_type="date",
        required=False,
        aliases=["line_service_date", "service_from_date"],
        description="Date procedure was performed",
    ),
    "quantity": OMOPField(
        omop_field="quantity",
        field_type="int",
        required=False,
        aliases=["units", "service_units", "qty", "unit_count"],
        description="Number of units/services",
    ),
    "modifier_source_value": OMOPField(
        omop_field="modifier_source_value",
        field_type="str",
        required=False,
        aliases=["modifier", "modifier_1", "modifier1", "mod1"],
        description="Procedure modifier code",
    ),
    "modifier_2": OMOPField(
        omop_field="modifier_2",
        field_type="str",
        required=False,
        aliases=["modifier_2", "modifier2", "mod2"],
        description="Second procedure modifier",
    ),
    "modifier_3": OMOPField(
        omop_field="modifier_3",
        field_type="str",
        required=False,
        aliases=["modifier_3", "modifier3", "mod3"],
        description="Third procedure modifier",
    ),
    "modifier_4": OMOPField(
        omop_field="modifier_4",
        field_type="str",
        required=False,
        aliases=["modifier_4", "modifier4", "mod4"],
        description="Fourth procedure modifier",
    ),
}

CONDITION_OCCURRENCE_FIELDS = {
    "condition_source_value": OMOPField(
        omop_field="condition_source_value",
        field_type="str",
        required=False,
        aliases=[
            "diagnosis_code",
            "dx_code",
            "icd_code",
            "icd10_code",
            "DiagnosisCode",
            "principal_diagnosis",
        ],
        description="Source diagnosis code (ICD-10)",
    ),
    "condition_source_value_list": OMOPField(
        omop_field="condition_source_value_list",
        field_type="list[str]",
        required=False,
        aliases=[
            "diagnosis_codes",
            "dx_codes",
            "icd_codes",
            "diagnoses",
        ],
        description="List of diagnosis codes",
    ),
}

PROVIDER_FIELDS = {
    "provider_id": OMOPField(
        omop_field="provider_id",
        field_type="str",
        required=False,
        aliases=[],
        description="Internal provider ID",
    ),
    "npi": OMOPField(
        omop_field="npi",
        field_type="str",
        required=True,
        aliases=[
            "provider_npi",
            "rendering_npi",
            "billing_npi",
            "attending_npi",
            "rendering_provider_npi",
            "billing_provider_npi",
            "ProviderNPI",
            "NPI",
        ],
        description="National Provider Identifier",
    ),
    "specialty_source_value": OMOPField(
        omop_field="specialty_source_value",
        field_type="str",
        required=False,
        aliases=[
            "specialty",
            "provider_specialty",
            "specialty_code",
            "taxonomy_code",
        ],
        description="Provider specialty/taxonomy",
    ),
}

COST_FIELDS = {
    "total_charge": OMOPField(
        omop_field="total_charge",
        field_type="float",
        required=False,
        aliases=[
            "billed_amount",
            "charge_amount",
            "total_amount",
            "claim_amount",
            "BilledAmount",
            "ChargeAmount",
        ],
        description="Total charged/billed amount",
    ),
    "total_cost": OMOPField(
        omop_field="total_cost",
        field_type="float",
        required=False,
        aliases=["allowed_amount", "paid_amount", "payment_amount"],
        description="Total cost/allowed amount",
    ),
    "line_charge": OMOPField(
        omop_field="line_charge",
        field_type="float",
        required=False,
        aliases=[
            "line_amount",
            "line_charge_amount",
            "service_charge",
            "LineAmount",
        ],
        description="Line-level charge amount",
    ),
}

PAYER_PLAN_FIELDS = {
    "payer_plan_period_id": OMOPField(
        omop_field="payer_plan_period_id",
        field_type="str",
        required=False,
        aliases=["plan_id", "coverage_id", "insurance_id"],
        description="Payer plan period identifier",
    ),
    "payer_source_value": OMOPField(
        omop_field="payer_source_value",
        field_type="str",
        required=False,
        aliases=["payer_id", "payer_name", "insurance_name"],
        description="Payer/insurance source value",
    ),
}

PERSON_FIELDS = {
    "year_of_birth": OMOPField(
        omop_field="year_of_birth",
        field_type="int",
        required=False,
        aliases=[],
        description="Year of birth",
    ),
    "birth_datetime": OMOPField(
        omop_field="birth_datetime",
        field_type="date",
        required=False,
        aliases=["dob", "date_of_birth", "birth_date", "DateOfBirth"],
        description="Date of birth",
    ),
    "gender_source_value": OMOPField(
        omop_field="gender_source_value",
        field_type="str",
        required=False,
        aliases=["gender", "sex", "member_gender"],
        description="Gender/sex",
    ),
    "age": OMOPField(
        omop_field="age",
        field_type="int",
        required=False,
        aliases=["patient_age", "member_age"],
        description="Age at time of service",
    ),
}


# Combined schema for claims processing
OMOP_CLAIMS_SCHEMA: dict[str, OMOPField] = {
    **VISIT_OCCURRENCE_FIELDS,
    **PROCEDURE_OCCURRENCE_FIELDS,
    **CONDITION_OCCURRENCE_FIELDS,
    **PROVIDER_FIELDS,
    **COST_FIELDS,
    **PAYER_PLAN_FIELDS,
    **PERSON_FIELDS,
}


def get_all_aliases() -> dict[str, str]:
    """Build a reverse lookup from alias -> canonical field name.

    Returns:
        Dictionary mapping alias names to their canonical OMOP field names.
    """
    alias_map: dict[str, str] = {}
    for canonical_name, field_def in OMOP_CLAIMS_SCHEMA.items():
        # Add the canonical name itself
        alias_map[canonical_name.lower()] = canonical_name
        # Add all aliases
        for alias in field_def.aliases:
            alias_map[alias.lower()] = canonical_name
    return alias_map


def get_required_fields() -> list[str]:
    """Get list of required OMOP fields.

    Returns:
        List of field names that are marked as required.
    """
    return [
        name for name, field_def in OMOP_CLAIMS_SCHEMA.items() if field_def.required
    ]


# Pre-computed alias lookup for performance
ALIAS_LOOKUP = get_all_aliases()
REQUIRED_FIELDS = get_required_fields()
