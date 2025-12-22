"""EDI 837I (Institutional Claims) field mapping template.

The 837I transaction is used for institutional healthcare claims,
typically submitted on UB-04 form equivalent. This includes hospital
inpatient, outpatient, skilled nursing, and other facility claims.

Reference:
- X12 837 Institutional Implementation Guide
- UB-04 field mappings (FL = Form Locator)
"""

# EDI 837I to OMOP CDM field mappings
# Format: {"edi_field_name": "omop_canonical_name"}
EDI_837I_MAPPING: dict[str, str] = {
    # Claim/Visit level (2300 loop)
    "clm01": "visit_occurrence_id",  # Patient Control Number (FL 3a)
    "clm02": "total_charge",  # Total Claim Charge Amount (FL 47)
    "clm05_1": "visit_source_value",  # Facility Type Code (FL 4)
    "clm05_2": "care_site_id",  # Claim Frequency Code
    "clm06": "visit_type_concept_id",  # Provider/Supplier Signature
    "patient_control_number": "visit_occurrence_id",
    "medical_record_number": "visit_occurrence_id",
    "total_charges": "total_charge",
    "total_claim_charge_amount": "total_charge",
    # Type of Bill (FL 4)
    "clm05_3": "visit_source_value",  # Type of Bill
    "type_of_bill": "visit_source_value",
    "bill_type": "visit_source_value",
    "tob": "visit_source_value",
    # Patient/Subscriber (2010BA loop)
    "nm109": "person_id",  # Subscriber Identifier
    "subscriber_identifier": "person_id",
    "subscriber_id": "person_id",
    "insured_id": "person_id",
    "member_id": "person_id",
    # Patient Information (FL 8-17)
    "pat01": "birth_datetime",  # Patient DOB
    "pat02": "gender_source_value",  # Patient Gender
    "patient_date_of_birth": "birth_datetime",
    "patient_dob": "birth_datetime",
    "patient_gender": "gender_source_value",
    "patient_sex": "gender_source_value",
    # Admission/Service dates (FL 6, 12-14)
    "dtp03_096": "visit_start_date",  # Discharge Date
    "dtp03_434": "visit_start_date",  # Statement From Date (FL 6)
    "dtp03_435": "visit_end_date",  # Statement To Date (FL 6)
    "dtp03_435_discharge": "visit_end_date",  # Discharge Date
    "statement_from_date": "visit_start_date",
    "statement_to_date": "visit_end_date",
    "statement_covers_period_from": "visit_start_date",
    "statement_covers_period_to": "visit_end_date",
    "admission_date": "visit_start_date",
    "discharge_date": "visit_end_date",
    # Condition Codes (FL 18-28)
    "cl101": "visit_source_value",  # Condition Code
    "condition_codes": "visit_source_value",
    # Occurrence Codes and Dates (FL 31-36)
    "hi01_bp": "visit_source_value",  # Occurrence Code
    "occurrence_code": "visit_source_value",
    # Value Codes and Amounts (FL 39-41)
    "hi01_be": "visit_source_value",  # Value Code
    "value_code": "visit_source_value",
    # Diagnosis Codes (FL 66-67, 69-75)
    "hi01_2_bk": "condition_source_value",  # Principal Diagnosis (FL 67)
    "hi02_2_bf": "condition_source_value",  # Admitting Diagnosis (FL 69)
    "principal_diagnosis": "condition_source_value",
    "principal_diagnosis_code": "condition_source_value",
    "admitting_diagnosis": "condition_source_value",
    "admitting_diagnosis_code": "condition_source_value",
    "diagnosis_code_1": "condition_source_value",
    "icd_principal": "condition_source_value",
    "icd10_principal": "condition_source_value",
    # Procedure Codes (FL 74)
    "hi01_2_bbr": "procedure_source_value",  # Principal Procedure
    "principal_procedure": "procedure_source_value",
    "principal_procedure_code": "procedure_source_value",
    "icd_procedure_1": "procedure_source_value",
    # Attending Physician (FL 76)
    "nm109_71": "npi",  # Attending Provider NPI
    "attending_provider_npi": "npi",
    "attending_npi": "npi",
    "attending_physician_npi": "npi",
    # Operating Physician (FL 77)
    "nm109_72": "npi",  # Operating Provider NPI
    "operating_provider_npi": "npi",
    "operating_npi": "npi",
    "surgeon_npi": "npi",
    # Other Provider (FL 78-79)
    "nm109_zz": "npi",  # Other Provider NPI
    "other_provider_npi": "npi",
    # Provider Taxonomy
    "prv03": "specialty_source_value",
    "provider_taxonomy": "specialty_source_value",
    "taxonomy_code": "specialty_source_value",
    # Service Line Items (2400 loop) - Revenue Codes (FL 42)
    "sv201": "procedure_source_value",  # Revenue Code
    "sv202_1": "procedure_source_value",  # HCPCS Code
    "sv202_2": "modifier_source_value",  # Modifier 1
    "sv202_3": "modifier_2",  # Modifier 2
    "sv203": "line_charge",  # Line Item Charge Amount
    "sv205": "quantity",  # Service Unit Count
    "revenue_code": "procedure_source_value",
    "rev_code": "procedure_source_value",
    "hcpcs_code": "procedure_source_value",
    "procedure_code": "procedure_source_value",
    "cpt_code": "procedure_source_value",
    "service_code": "procedure_source_value",
    "modifier_1": "modifier_source_value",
    "modifier_2": "modifier_2",
    "line_charge_amount": "line_charge",
    "service_charge": "line_charge",
    "charge_amount": "line_charge",
    "units": "quantity",
    "service_units": "quantity",
    "covered_days": "quantity",
    "non_covered_days": "quantity",
    # Service Dates (FL 45)
    "dtp03_472": "procedure_date",  # Service Date
    "service_date": "procedure_date",
    "service_from_date": "procedure_date",
    "service_to_date": "procedure_date",
    # Payer Information (FL 50-57)
    "nm103": "payer_source_value",  # Payer Name
    "payer_name": "payer_source_value",
    "insurance_name": "payer_source_value",
    "primary_payer_name": "payer_source_value",
    "payer_id": "payer_plan_period_id",
    # DRG (FL 71)
    "hi01_dr": "visit_source_value",  # DRG Code
    "drg_code": "visit_source_value",
    "drg": "visit_source_value",
}

# UB-04 Form Locator reference
UB04_FORM_LOCATORS: dict[str, str] = {
    "FL1": "Billing Provider Name/Address",
    "FL3a": "Patient Control Number",
    "FL4": "Type of Bill",
    "FL6": "Statement Covers Period",
    "FL8-11": "Patient Name/Address",
    "FL12-13": "Admission/Start of Care Date",
    "FL14": "Priority (Type) of Admission/Visit",
    "FL15": "Point of Origin",
    "FL17": "Patient Discharge Status",
    "FL18-28": "Condition Codes",
    "FL31-36": "Occurrence Codes and Dates",
    "FL39-41": "Value Codes and Amounts",
    "FL42": "Revenue Code",
    "FL43": "Revenue Description",
    "FL44": "HCPCS/Rate/HIPPS Code",
    "FL45": "Service Date",
    "FL46": "Service Units",
    "FL47": "Total Charges",
    "FL50": "Payer Name",
    "FL58": "Insured's Name",
    "FL60": "Insured's Unique ID",
    "FL66": "Diagnosis/Procedure Code Qualifier",
    "FL67": "Principal Diagnosis Code",
    "FL69": "Admitting Diagnosis Code",
    "FL74": "Principal Procedure Code/Date",
    "FL76": "Attending Provider NPI/Name",
    "FL77": "Operating Provider NPI/Name",
}
