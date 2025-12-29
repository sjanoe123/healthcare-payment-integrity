-- =====================================================
-- Kirk AI Test Tables
-- Comprehensive denormalized claims for fraud detection testing
-- =====================================================

-- Drop existing tables if they exist
DROP TABLE IF EXISTS kirk_eval CASCADE;
DROP TABLE IF EXISTS kirk_test CASCADE;

-- =====================================================
-- KIRK_TEST: Claims for Kirk to analyze (no fraud hints)
-- =====================================================
CREATE TABLE kirk_test (
    -- Claim Identifiers
    claim_id VARCHAR(50) PRIMARY KEY,
    claim_control_number VARCHAR(50),
    original_reference_number VARCHAR(50),

    -- Claim Type & Form
    claim_type VARCHAR(10),  -- 837P (Professional), 837I (Institutional)
    claim_frequency_code VARCHAR(2),  -- 1=Original, 7=Replacement, 8=Void
    bill_type_code VARCHAR(4),  -- UB-04 bill type (e.g., 0111, 0121)

    -- Dates
    statement_from_date DATE,
    statement_to_date DATE,
    admission_date DATE,
    discharge_date DATE,
    received_date DATE,
    paid_date DATE,

    -- Patient/Member Information
    member_id VARCHAR(50),
    patient_first_name VARCHAR(100),
    patient_last_name VARCHAR(100),
    patient_dob DATE,
    patient_age INTEGER,
    patient_gender VARCHAR(1),  -- M, F, U
    patient_address VARCHAR(200),
    patient_city VARCHAR(100),
    patient_state VARCHAR(2),
    patient_zip VARCHAR(10),
    patient_relationship_to_subscriber VARCHAR(2),  -- 18=Self, 01=Spouse, etc.

    -- Subscriber Information
    subscriber_id VARCHAR(50),
    subscriber_first_name VARCHAR(100),
    subscriber_last_name VARCHAR(100),
    subscriber_dob DATE,
    subscriber_gender VARCHAR(1),
    group_number VARCHAR(50),
    group_name VARCHAR(200),

    -- Insurance/Payer Information
    payer_id VARCHAR(50),
    payer_name VARCHAR(200),
    plan_id VARCHAR(50),
    plan_name VARCHAR(200),
    plan_type VARCHAR(20),  -- HMO, PPO, POS, EPO, Medicare, Medicaid
    coverage_type VARCHAR(20),  -- Primary, Secondary, Tertiary

    -- Billing Provider
    billing_provider_npi VARCHAR(10),
    billing_provider_name VARCHAR(200),
    billing_provider_taxonomy VARCHAR(15),
    billing_provider_specialty VARCHAR(200),
    billing_provider_address VARCHAR(200),
    billing_provider_city VARCHAR(100),
    billing_provider_state VARCHAR(2),
    billing_provider_zip VARCHAR(10),
    billing_provider_tax_id VARCHAR(15),

    -- Rendering Provider (who performed the service)
    rendering_provider_npi VARCHAR(10),
    rendering_provider_name VARCHAR(200),
    rendering_provider_taxonomy VARCHAR(15),
    rendering_provider_specialty VARCHAR(200),
    rendering_provider_credential VARCHAR(20),

    -- Referring Provider
    referring_provider_npi VARCHAR(10),
    referring_provider_name VARCHAR(200),

    -- Facility/Service Location
    facility_npi VARCHAR(10),
    facility_name VARCHAR(200),
    facility_address VARCHAR(200),
    facility_city VARCHAR(100),
    facility_state VARCHAR(2),
    facility_zip VARCHAR(10),
    facility_type VARCHAR(50),

    -- Place of Service
    place_of_service_code VARCHAR(2),
    place_of_service_name VARCHAR(100),

    -- Admission Information (Institutional)
    admission_type_code VARCHAR(2),  -- 1=Emergency, 2=Urgent, 3=Elective, etc.
    admission_source_code VARCHAR(2),  -- 1=Physician referral, 2=Clinic, etc.
    discharge_status_code VARCHAR(2),  -- 01=Home, 02=SNF, 20=Expired, etc.
    patient_status_code VARCHAR(2),

    -- DRG Information (Inpatient)
    drg_code VARCHAR(10),
    drg_description VARCHAR(200),
    drg_weight DECIMAL(8,4),

    -- Diagnosis Codes (ICD-10-CM)
    principal_diagnosis_code VARCHAR(10),
    principal_diagnosis_description VARCHAR(200),
    admitting_diagnosis_code VARCHAR(10),
    diagnosis_code_2 VARCHAR(10),
    diagnosis_code_3 VARCHAR(10),
    diagnosis_code_4 VARCHAR(10),
    diagnosis_code_5 VARCHAR(10),
    diagnosis_code_6 VARCHAR(10),
    diagnosis_code_7 VARCHAR(10),
    diagnosis_code_8 VARCHAR(10),
    diagnosis_code_9 VARCHAR(10),
    diagnosis_code_10 VARCHAR(10),
    diagnosis_code_11 VARCHAR(10),
    diagnosis_code_12 VARCHAR(10),
    diagnosis_present_on_admission VARCHAR(12),  -- Y/N flags for each dx

    -- External Cause Codes
    external_cause_code_1 VARCHAR(10),
    external_cause_code_2 VARCHAR(10),

    -- Procedure Codes (ICD-10-PCS for Inpatient)
    principal_procedure_code VARCHAR(10),
    principal_procedure_date DATE,
    procedure_code_2 VARCHAR(10),
    procedure_date_2 DATE,
    procedure_code_3 VARCHAR(10),
    procedure_date_3 DATE,

    -- Service Lines (denormalized - up to 10 lines)
    -- Line 1
    line_1_procedure_code VARCHAR(10),
    line_1_procedure_description VARCHAR(200),
    line_1_modifier_1 VARCHAR(2),
    line_1_modifier_2 VARCHAR(2),
    line_1_modifier_3 VARCHAR(2),
    line_1_modifier_4 VARCHAR(2),
    line_1_revenue_code VARCHAR(4),
    line_1_revenue_description VARCHAR(100),
    line_1_service_date DATE,
    line_1_service_date_end DATE,
    line_1_place_of_service VARCHAR(2),
    line_1_units DECIMAL(10,3),
    line_1_unit_type VARCHAR(10),  -- UN=Units, MJ=Minutes, etc.
    line_1_charge_amount DECIMAL(12,2),
    line_1_allowed_amount DECIMAL(12,2),
    line_1_ndc_code VARCHAR(12),
    line_1_ndc_quantity DECIMAL(10,3),
    line_1_ndc_unit VARCHAR(5),
    line_1_diagnosis_pointer VARCHAR(10),
    line_1_rendering_provider_npi VARCHAR(10),

    -- Line 2
    line_2_procedure_code VARCHAR(10),
    line_2_procedure_description VARCHAR(200),
    line_2_modifier_1 VARCHAR(2),
    line_2_modifier_2 VARCHAR(2),
    line_2_modifier_3 VARCHAR(2),
    line_2_modifier_4 VARCHAR(2),
    line_2_revenue_code VARCHAR(4),
    line_2_revenue_description VARCHAR(100),
    line_2_service_date DATE,
    line_2_service_date_end DATE,
    line_2_place_of_service VARCHAR(2),
    line_2_units DECIMAL(10,3),
    line_2_unit_type VARCHAR(10),
    line_2_charge_amount DECIMAL(12,2),
    line_2_allowed_amount DECIMAL(12,2),
    line_2_ndc_code VARCHAR(12),
    line_2_ndc_quantity DECIMAL(10,3),
    line_2_ndc_unit VARCHAR(5),
    line_2_diagnosis_pointer VARCHAR(10),
    line_2_rendering_provider_npi VARCHAR(10),

    -- Line 3
    line_3_procedure_code VARCHAR(10),
    line_3_procedure_description VARCHAR(200),
    line_3_modifier_1 VARCHAR(2),
    line_3_modifier_2 VARCHAR(2),
    line_3_modifier_3 VARCHAR(2),
    line_3_modifier_4 VARCHAR(2),
    line_3_revenue_code VARCHAR(4),
    line_3_revenue_description VARCHAR(100),
    line_3_service_date DATE,
    line_3_service_date_end DATE,
    line_3_place_of_service VARCHAR(2),
    line_3_units DECIMAL(10,3),
    line_3_unit_type VARCHAR(10),
    line_3_charge_amount DECIMAL(12,2),
    line_3_allowed_amount DECIMAL(12,2),
    line_3_ndc_code VARCHAR(12),
    line_3_ndc_quantity DECIMAL(10,3),
    line_3_ndc_unit VARCHAR(5),
    line_3_diagnosis_pointer VARCHAR(10),
    line_3_rendering_provider_npi VARCHAR(10),

    -- Line 4
    line_4_procedure_code VARCHAR(10),
    line_4_procedure_description VARCHAR(200),
    line_4_modifier_1 VARCHAR(2),
    line_4_modifier_2 VARCHAR(2),
    line_4_modifier_3 VARCHAR(2),
    line_4_modifier_4 VARCHAR(2),
    line_4_revenue_code VARCHAR(4),
    line_4_revenue_description VARCHAR(100),
    line_4_service_date DATE,
    line_4_service_date_end DATE,
    line_4_place_of_service VARCHAR(2),
    line_4_units DECIMAL(10,3),
    line_4_unit_type VARCHAR(10),
    line_4_charge_amount DECIMAL(12,2),
    line_4_allowed_amount DECIMAL(12,2),
    line_4_ndc_code VARCHAR(12),
    line_4_ndc_quantity DECIMAL(10,3),
    line_4_ndc_unit VARCHAR(5),
    line_4_diagnosis_pointer VARCHAR(10),
    line_4_rendering_provider_npi VARCHAR(10),

    -- Line 5
    line_5_procedure_code VARCHAR(10),
    line_5_procedure_description VARCHAR(200),
    line_5_modifier_1 VARCHAR(2),
    line_5_modifier_2 VARCHAR(2),
    line_5_modifier_3 VARCHAR(2),
    line_5_modifier_4 VARCHAR(2),
    line_5_revenue_code VARCHAR(4),
    line_5_revenue_description VARCHAR(100),
    line_5_service_date DATE,
    line_5_service_date_end DATE,
    line_5_place_of_service VARCHAR(2),
    line_5_units DECIMAL(10,3),
    line_5_unit_type VARCHAR(10),
    line_5_charge_amount DECIMAL(12,2),
    line_5_allowed_amount DECIMAL(12,2),
    line_5_ndc_code VARCHAR(12),
    line_5_ndc_quantity DECIMAL(10,3),
    line_5_ndc_unit VARCHAR(5),
    line_5_diagnosis_pointer VARCHAR(10),
    line_5_rendering_provider_npi VARCHAR(10),

    -- Financial Summary
    total_charge_amount DECIMAL(12,2),
    total_allowed_amount DECIMAL(12,2),
    total_paid_amount DECIMAL(12,2),
    patient_responsibility DECIMAL(12,2),
    copay_amount DECIMAL(12,2),
    coinsurance_amount DECIMAL(12,2),
    deductible_amount DECIMAL(12,2),

    -- COB (Coordination of Benefits)
    other_payer_id VARCHAR(50),
    other_payer_name VARCHAR(200),
    other_payer_paid_amount DECIMAL(12,2),
    cob_adjustment_amount DECIMAL(12,2),

    -- Prior Authorization
    prior_auth_number VARCHAR(50),
    prior_auth_status VARCHAR(20),
    prior_auth_date DATE,
    prior_auth_expiration_date DATE,

    -- Accident/Condition Information
    accident_date DATE,
    accident_state VARCHAR(2),
    accident_type VARCHAR(20),  -- Auto, Work, Other
    last_menstrual_period DATE,
    disability_from_date DATE,
    disability_to_date DATE,
    hospitalization_from_date DATE,
    hospitalization_to_date DATE,

    -- Additional Clinical Information
    condition_codes JSONB,  -- Array of condition codes
    occurrence_codes JSONB,  -- Array of occurrence codes and dates
    value_codes JSONB,  -- Array of value codes and amounts

    -- Remarks/Notes
    claim_note TEXT,
    attachment_control_number VARCHAR(50),

    -- Service Line Count
    total_service_lines INTEGER,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- KIRK_EVAL: Same claims WITH fraud scenario labels
-- For evaluating Kirk's detection accuracy
-- =====================================================
CREATE TABLE kirk_eval (
    -- All the same fields as kirk_test
    claim_id VARCHAR(50) PRIMARY KEY,
    claim_control_number VARCHAR(50),
    original_reference_number VARCHAR(50),
    claim_type VARCHAR(10),
    claim_frequency_code VARCHAR(2),
    bill_type_code VARCHAR(4),
    statement_from_date DATE,
    statement_to_date DATE,
    admission_date DATE,
    discharge_date DATE,
    received_date DATE,
    paid_date DATE,
    member_id VARCHAR(50),
    patient_first_name VARCHAR(100),
    patient_last_name VARCHAR(100),
    patient_dob DATE,
    patient_age INTEGER,
    patient_gender VARCHAR(1),
    patient_address VARCHAR(200),
    patient_city VARCHAR(100),
    patient_state VARCHAR(2),
    patient_zip VARCHAR(10),
    patient_relationship_to_subscriber VARCHAR(2),
    subscriber_id VARCHAR(50),
    subscriber_first_name VARCHAR(100),
    subscriber_last_name VARCHAR(100),
    subscriber_dob DATE,
    subscriber_gender VARCHAR(1),
    group_number VARCHAR(50),
    group_name VARCHAR(200),
    payer_id VARCHAR(50),
    payer_name VARCHAR(200),
    plan_id VARCHAR(50),
    plan_name VARCHAR(200),
    plan_type VARCHAR(20),
    coverage_type VARCHAR(20),
    billing_provider_npi VARCHAR(10),
    billing_provider_name VARCHAR(200),
    billing_provider_taxonomy VARCHAR(15),
    billing_provider_specialty VARCHAR(200),
    billing_provider_address VARCHAR(200),
    billing_provider_city VARCHAR(100),
    billing_provider_state VARCHAR(2),
    billing_provider_zip VARCHAR(10),
    billing_provider_tax_id VARCHAR(15),
    rendering_provider_npi VARCHAR(10),
    rendering_provider_name VARCHAR(200),
    rendering_provider_taxonomy VARCHAR(15),
    rendering_provider_specialty VARCHAR(200),
    rendering_provider_credential VARCHAR(20),
    referring_provider_npi VARCHAR(10),
    referring_provider_name VARCHAR(200),
    facility_npi VARCHAR(10),
    facility_name VARCHAR(200),
    facility_address VARCHAR(200),
    facility_city VARCHAR(100),
    facility_state VARCHAR(2),
    facility_zip VARCHAR(10),
    facility_type VARCHAR(50),
    place_of_service_code VARCHAR(2),
    place_of_service_name VARCHAR(100),
    admission_type_code VARCHAR(2),
    admission_source_code VARCHAR(2),
    discharge_status_code VARCHAR(2),
    patient_status_code VARCHAR(2),
    drg_code VARCHAR(10),
    drg_description VARCHAR(200),
    drg_weight DECIMAL(8,4),
    principal_diagnosis_code VARCHAR(10),
    principal_diagnosis_description VARCHAR(200),
    admitting_diagnosis_code VARCHAR(10),
    diagnosis_code_2 VARCHAR(10),
    diagnosis_code_3 VARCHAR(10),
    diagnosis_code_4 VARCHAR(10),
    diagnosis_code_5 VARCHAR(10),
    diagnosis_code_6 VARCHAR(10),
    diagnosis_code_7 VARCHAR(10),
    diagnosis_code_8 VARCHAR(10),
    diagnosis_code_9 VARCHAR(10),
    diagnosis_code_10 VARCHAR(10),
    diagnosis_code_11 VARCHAR(10),
    diagnosis_code_12 VARCHAR(10),
    diagnosis_present_on_admission VARCHAR(12),
    external_cause_code_1 VARCHAR(10),
    external_cause_code_2 VARCHAR(10),
    principal_procedure_code VARCHAR(10),
    principal_procedure_date DATE,
    procedure_code_2 VARCHAR(10),
    procedure_date_2 DATE,
    procedure_code_3 VARCHAR(10),
    procedure_date_3 DATE,
    line_1_procedure_code VARCHAR(10),
    line_1_procedure_description VARCHAR(200),
    line_1_modifier_1 VARCHAR(2),
    line_1_modifier_2 VARCHAR(2),
    line_1_modifier_3 VARCHAR(2),
    line_1_modifier_4 VARCHAR(2),
    line_1_revenue_code VARCHAR(4),
    line_1_revenue_description VARCHAR(100),
    line_1_service_date DATE,
    line_1_service_date_end DATE,
    line_1_place_of_service VARCHAR(2),
    line_1_units DECIMAL(10,3),
    line_1_unit_type VARCHAR(10),
    line_1_charge_amount DECIMAL(12,2),
    line_1_allowed_amount DECIMAL(12,2),
    line_1_ndc_code VARCHAR(12),
    line_1_ndc_quantity DECIMAL(10,3),
    line_1_ndc_unit VARCHAR(5),
    line_1_diagnosis_pointer VARCHAR(10),
    line_1_rendering_provider_npi VARCHAR(10),
    line_2_procedure_code VARCHAR(10),
    line_2_procedure_description VARCHAR(200),
    line_2_modifier_1 VARCHAR(2),
    line_2_modifier_2 VARCHAR(2),
    line_2_modifier_3 VARCHAR(2),
    line_2_modifier_4 VARCHAR(2),
    line_2_revenue_code VARCHAR(4),
    line_2_revenue_description VARCHAR(100),
    line_2_service_date DATE,
    line_2_service_date_end DATE,
    line_2_place_of_service VARCHAR(2),
    line_2_units DECIMAL(10,3),
    line_2_unit_type VARCHAR(10),
    line_2_charge_amount DECIMAL(12,2),
    line_2_allowed_amount DECIMAL(12,2),
    line_2_ndc_code VARCHAR(12),
    line_2_ndc_quantity DECIMAL(10,3),
    line_2_ndc_unit VARCHAR(5),
    line_2_diagnosis_pointer VARCHAR(10),
    line_2_rendering_provider_npi VARCHAR(10),
    line_3_procedure_code VARCHAR(10),
    line_3_procedure_description VARCHAR(200),
    line_3_modifier_1 VARCHAR(2),
    line_3_modifier_2 VARCHAR(2),
    line_3_modifier_3 VARCHAR(2),
    line_3_modifier_4 VARCHAR(2),
    line_3_revenue_code VARCHAR(4),
    line_3_revenue_description VARCHAR(100),
    line_3_service_date DATE,
    line_3_service_date_end DATE,
    line_3_place_of_service VARCHAR(2),
    line_3_units DECIMAL(10,3),
    line_3_unit_type VARCHAR(10),
    line_3_charge_amount DECIMAL(12,2),
    line_3_allowed_amount DECIMAL(12,2),
    line_3_ndc_code VARCHAR(12),
    line_3_ndc_quantity DECIMAL(10,3),
    line_3_ndc_unit VARCHAR(5),
    line_3_diagnosis_pointer VARCHAR(10),
    line_3_rendering_provider_npi VARCHAR(10),
    line_4_procedure_code VARCHAR(10),
    line_4_procedure_description VARCHAR(200),
    line_4_modifier_1 VARCHAR(2),
    line_4_modifier_2 VARCHAR(2),
    line_4_modifier_3 VARCHAR(2),
    line_4_modifier_4 VARCHAR(2),
    line_4_revenue_code VARCHAR(4),
    line_4_revenue_description VARCHAR(100),
    line_4_service_date DATE,
    line_4_service_date_end DATE,
    line_4_place_of_service VARCHAR(2),
    line_4_units DECIMAL(10,3),
    line_4_unit_type VARCHAR(10),
    line_4_charge_amount DECIMAL(12,2),
    line_4_allowed_amount DECIMAL(12,2),
    line_4_ndc_code VARCHAR(12),
    line_4_ndc_quantity DECIMAL(10,3),
    line_4_ndc_unit VARCHAR(5),
    line_4_diagnosis_pointer VARCHAR(10),
    line_4_rendering_provider_npi VARCHAR(10),
    line_5_procedure_code VARCHAR(10),
    line_5_procedure_description VARCHAR(200),
    line_5_modifier_1 VARCHAR(2),
    line_5_modifier_2 VARCHAR(2),
    line_5_modifier_3 VARCHAR(2),
    line_5_modifier_4 VARCHAR(2),
    line_5_revenue_code VARCHAR(4),
    line_5_revenue_description VARCHAR(100),
    line_5_service_date DATE,
    line_5_service_date_end DATE,
    line_5_place_of_service VARCHAR(2),
    line_5_units DECIMAL(10,3),
    line_5_unit_type VARCHAR(10),
    line_5_charge_amount DECIMAL(12,2),
    line_5_allowed_amount DECIMAL(12,2),
    line_5_ndc_code VARCHAR(12),
    line_5_ndc_quantity DECIMAL(10,3),
    line_5_ndc_unit VARCHAR(5),
    line_5_diagnosis_pointer VARCHAR(10),
    line_5_rendering_provider_npi VARCHAR(10),
    total_charge_amount DECIMAL(12,2),
    total_allowed_amount DECIMAL(12,2),
    total_paid_amount DECIMAL(12,2),
    patient_responsibility DECIMAL(12,2),
    copay_amount DECIMAL(12,2),
    coinsurance_amount DECIMAL(12,2),
    deductible_amount DECIMAL(12,2),
    other_payer_id VARCHAR(50),
    other_payer_name VARCHAR(200),
    other_payer_paid_amount DECIMAL(12,2),
    cob_adjustment_amount DECIMAL(12,2),
    prior_auth_number VARCHAR(50),
    prior_auth_status VARCHAR(20),
    prior_auth_date DATE,
    prior_auth_expiration_date DATE,
    accident_date DATE,
    accident_state VARCHAR(2),
    accident_type VARCHAR(20),
    last_menstrual_period DATE,
    disability_from_date DATE,
    disability_to_date DATE,
    hospitalization_from_date DATE,
    hospitalization_to_date DATE,
    condition_codes JSONB,
    occurrence_codes JSONB,
    value_codes JSONB,
    claim_note TEXT,
    attachment_control_number VARCHAR(50),
    total_service_lines INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- =====================================================
    -- EVALUATION FIELDS (only in kirk_eval, not kirk_test)
    -- =====================================================
    fraud_scenario_type VARCHAR(50),  -- oig_excluded, ncci_ptp_violation, etc.
    fraud_risk_level VARCHAR(20),  -- high, medium, clean
    expected_rule_triggers JSONB,  -- Array of expected rule IDs
    scenario_details JSONB,  -- Specific details about the fraud scenario
    ground_truth_fraud_score DECIMAL(5,4)  -- Expected fraud score 0.0-1.0
);

-- Create indexes for kirk tables
CREATE INDEX idx_kirk_test_claim_id ON kirk_test(claim_id);
CREATE INDEX idx_kirk_test_member_id ON kirk_test(member_id);
CREATE INDEX idx_kirk_test_billing_npi ON kirk_test(billing_provider_npi);
CREATE INDEX idx_kirk_test_service_date ON kirk_test(statement_from_date);

CREATE INDEX idx_kirk_eval_claim_id ON kirk_eval(claim_id);
CREATE INDEX idx_kirk_eval_scenario_type ON kirk_eval(fraud_scenario_type);
CREATE INDEX idx_kirk_eval_risk_level ON kirk_eval(fraud_risk_level);
