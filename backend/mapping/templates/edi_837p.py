"""EDI 837P (Professional Claims) field mapping template.

The 837P transaction is used for professional healthcare claims,
typically submitted on CMS-1500 form equivalent. This mapping
covers the standard X12 837P loop and segment field names.

Reference:
- X12 837 Professional Implementation Guide
- CMS-1500 field mappings
"""

# EDI 837P to OMOP CDM field mappings
# Format: {"edi_field_name": "omop_canonical_name"}
EDI_837P_MAPPING: dict[str, str] = {
    # Claim/Visit level (2300 loop)
    "clm01": "visit_occurrence_id",  # Claim ID
    "clm02": "total_charge",  # Total Claim Charge Amount
    "clm05_1": "visit_source_value",  # Facility Type Code
    "clm05_2": "care_site_id",  # Facility Code Qualifier
    "claim_submitter_identifier": "visit_occurrence_id",
    "total_claim_charge_amount": "total_charge",
    "claim_frequency_type_code": "visit_source_value",
    # Patient/Subscriber (2010BA loop)
    "nm109": "person_id",  # Subscriber Identifier
    "subscriber_identifier": "person_id",
    "subscriber_primary_identifier": "person_id",
    "patient_control_number": "visit_occurrence_id",
    "insured_id": "person_id",
    # Demographics (2010CA loop if different from subscriber)
    "dmg02": "birth_datetime",  # Patient DOB
    "dmg03": "gender_source_value",  # Patient Gender
    "patient_date_of_birth": "birth_datetime",
    "patient_gender_code": "gender_source_value",
    # Service dates (2300 loop)
    "dtp03_472": "visit_start_date",  # Service Date (qualifier 472)
    "dtp03_434": "visit_start_date",  # Statement Date From (qualifier 434)
    "dtp03_435": "visit_end_date",  # Statement Date To (qualifier 435)
    "statement_from_date": "visit_start_date",
    "statement_to_date": "visit_end_date",
    "service_date": "visit_start_date",
    "date_of_service": "visit_start_date",
    "dos": "visit_start_date",
    # Diagnosis codes (2300 loop - HI segment)
    "hi01_2": "condition_source_value",  # Principal Diagnosis
    "hi02_2": "condition_source_value",  # Other Diagnosis 1
    "principal_diagnosis_code": "condition_source_value",
    "diagnosis_code_1": "condition_source_value",
    "icd_principal": "condition_source_value",
    # Rendering Provider (2310B loop)
    "nm109_82": "npi",  # Rendering Provider NPI (qualifier 82)
    "ref02_1c": "npi",  # Rendering Provider Secondary ID
    "rendering_provider_npi": "npi",
    "rendering_npi": "npi",
    "provider_npi": "npi",
    # Rendering Provider Specialty
    "prv03": "specialty_source_value",  # Provider Taxonomy Code
    "rendering_provider_taxonomy": "specialty_source_value",
    "provider_taxonomy": "specialty_source_value",
    "taxonomy_code": "specialty_source_value",
    # Billing Provider (2010AA loop)
    "nm109_85": "npi",  # Billing Provider NPI (qualifier 85)
    "billing_provider_npi": "npi",
    "billing_npi": "npi",
    # Service Line Items (2400 loop)
    "sv101_1": "procedure_source_value",  # CPT/HCPCS Code (qualifier HC)
    "sv101_2": "modifier_source_value",  # Modifier 1
    "sv101_3": "modifier_2",  # Modifier 2
    "sv101_4": "modifier_3",  # Modifier 3
    "sv101_5": "modifier_4",  # Modifier 4
    "sv102": "line_charge",  # Line Item Charge Amount
    "sv104": "quantity",  # Service Unit Count
    "sv107": "condition_source_value",  # Line Diagnosis Code Pointer
    "procedure_code": "procedure_source_value",
    "cpt_code": "procedure_source_value",
    "hcpcs_code": "procedure_source_value",
    "service_code": "procedure_source_value",
    "modifier_1": "modifier_source_value",
    "modifier_2": "modifier_2",
    "modifier_3": "modifier_3",
    "modifier_4": "modifier_4",
    "line_charge_amount": "line_charge",
    "charge_amount": "line_charge",
    "billed_amount": "total_charge",
    "units": "quantity",
    "service_units": "quantity",
    "unit_count": "quantity",
    # Service Line Dates (2400 loop)
    "dtp03_472_line": "procedure_date",  # Line Service Date
    "service_from_date": "procedure_date",
    "line_service_date": "procedure_date",
    # Payer Information (2010BB loop)
    "nm103": "payer_source_value",  # Payer Name
    "payer_name": "payer_source_value",
    "insurance_name": "payer_source_value",
    "payer_id": "payer_plan_period_id",
}

# Field descriptions for documentation
EDI_837P_FIELD_DESCRIPTIONS: dict[str, str] = {
    "clm01": "Claim Submitter's Identifier - unique claim ID",
    "clm02": "Total Claim Charge Amount",
    "nm109": "Subscriber Primary Identifier",
    "dmg02": "Patient Date of Birth (CCYYMMDD)",
    "dmg03": "Patient Gender Code (M/F/U)",
    "dtp03_472": "Service Date (qualifier 472)",
    "hi01_2": "Health Care Diagnosis Code (ICD-10)",
    "sv101_1": "Composite Medical Procedure Identifier (CPT/HCPCS)",
    "prv03": "Provider Taxonomy Code",
}
