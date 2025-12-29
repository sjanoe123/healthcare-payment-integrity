-- =====================================================
-- Healthcare Payment Integrity Test Database Schema
-- Aligned with OMOP CDM and existing connector schemas
-- =====================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- PROVIDERS TABLE
-- Based on: backend/connectors expectations
-- =====================================================
CREATE TABLE providers (
    npi VARCHAR(10) PRIMARY KEY,
    provider_type VARCHAR(1) NOT NULL DEFAULT '1',  -- 1=Individual, 2=Organization
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    organization_name VARCHAR(200),
    credential VARCHAR(20),
    primary_taxonomy VARCHAR(15),
    specialty_description VARCHAR(200),
    practice_address_line1 VARCHAR(200),
    practice_city VARCHAR(100),
    practice_state VARCHAR(2),
    practice_zip VARCHAR(10),
    phone VARCHAR(20),
    enumeration_date DATE,
    last_update_date DATE,
    -- FWA fields (align with fwa_rules.py)
    is_oig_excluded BOOLEAN DEFAULT FALSE,
    exclusion_date DATE,
    exclusion_type VARCHAR(50),
    is_fwa_watchlist BOOLEAN DEFAULT FALSE,
    avg_monthly_claims DECIMAL(10,2) DEFAULT 0,
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- PROVIDER HISTORY TABLE
-- For volume spike detection (fwa_rules.py)
-- =====================================================
CREATE TABLE provider_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    npi VARCHAR(10) NOT NULL REFERENCES providers(npi),
    month_year VARCHAR(7) NOT NULL,  -- Format: YYYY-MM
    claim_count INTEGER DEFAULT 0,
    total_billed DECIMAL(12,2) DEFAULT 0,
    unique_members INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(npi, month_year)
);

-- =====================================================
-- ELIGIBILITY TABLE (Members)
-- Based on: backend/connectors expectations
-- =====================================================
CREATE TABLE eligibility (
    member_id VARCHAR(50) PRIMARY KEY,
    subscriber_id VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    date_of_birth DATE,
    gender VARCHAR(1),  -- M, F, U
    address_line1 VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    phone VARCHAR(20),
    email VARCHAR(200),
    -- Coverage status
    status VARCHAR(20) DEFAULT 'active',  -- active, inactive, terminated
    status_date DATE,
    -- Plan info
    plan_id VARCHAR(50),
    plan_name VARCHAR(200),
    group_number VARCHAR(50),
    effective_date DATE NOT NULL,
    termination_date DATE,
    payer_id VARCHAR(50),
    payer_name VARCHAR(200),
    -- Primary care
    pcp_npi VARCHAR(10) REFERENCES providers(npi),
    -- Coordination of benefits
    cob_order INTEGER DEFAULT 1,
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- BENEFIT LIMITS TABLE
-- For eligibility_benefit_limit_rule
-- =====================================================
CREATE TABLE benefit_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id VARCHAR(50) NOT NULL,
    procedure_code VARCHAR(10) NOT NULL,
    max_units INTEGER,
    max_amount DECIMAL(12,2),
    time_period VARCHAR(20) DEFAULT 'yearly',  -- yearly, quarterly, monthly
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(plan_id, procedure_code)
);

-- =====================================================
-- PRIOR AUTHORIZATION TABLE
-- For eligibility_no_auth_rule
-- =====================================================
CREATE TABLE prior_authorizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_id VARCHAR(50) NOT NULL REFERENCES eligibility(member_id),
    procedure_code VARCHAR(10) NOT NULL,
    auth_number VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'approved',  -- approved, pending, denied, expired
    auth_date DATE NOT NULL,
    expiration_date DATE,
    approved_units INTEGER,
    approved_amount DECIMAL(12,2),
    requesting_provider_npi VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- AUTHORIZATION REQUIRED CODES TABLE
-- For identifying which codes need prior auth
-- =====================================================
CREATE TABLE auth_required_codes (
    procedure_code VARCHAR(10) PRIMARY KEY,
    requires_auth BOOLEAN DEFAULT TRUE,
    auth_type VARCHAR(50),  -- prior, concurrent, retro
    description VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- CLAIMS TABLE (Header Level)
-- Based on: OMOP CDM visit_occurrence + claim fields
-- =====================================================
CREATE TABLE claims (
    claim_id VARCHAR(50) PRIMARY KEY,
    -- Member reference
    member_id VARCHAR(50) NOT NULL REFERENCES eligibility(member_id),
    -- Claim type
    claim_type VARCHAR(10) NOT NULL DEFAULT '837P',  -- 837P, 837I
    patient_control_number VARCHAR(50),
    -- Provider references
    billing_provider_npi VARCHAR(10) NOT NULL REFERENCES providers(npi),
    rendering_provider_npi VARCHAR(10) REFERENCES providers(npi),
    facility_npi VARCHAR(10) REFERENCES providers(npi),
    -- Dates
    statement_from_date DATE NOT NULL,
    statement_to_date DATE,
    received_date DATE DEFAULT CURRENT_DATE,
    -- Institutional fields
    admission_date DATE,
    discharge_date DATE,
    bill_type VARCHAR(4),
    drg_code VARCHAR(10),
    admission_type VARCHAR(2),
    discharge_status VARCHAR(2),
    -- Place of service
    place_of_service VARCHAR(2) DEFAULT '11',  -- Office
    -- Diagnoses (stored as JSON array)
    principal_diagnosis VARCHAR(10),
    diagnosis_codes JSONB DEFAULT '[]',
    -- Financial
    total_charge DECIMAL(12,2) DEFAULT 0,
    total_allowed DECIMAL(12,2),
    total_paid DECIMAL(12,2),
    -- Payer
    payer_plan_period_id VARCHAR(50),
    -- Metadata
    status VARCHAR(20) DEFAULT 'pending',
    source_file VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- CLAIM LINES TABLE (Service Line Level)
-- Based on: OMOP CDM procedure_occurrence + claim line fields
-- =====================================================
CREATE TABLE claim_lines (
    line_id VARCHAR(50) PRIMARY KEY,
    claim_id VARCHAR(50) NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    -- Procedure
    procedure_code VARCHAR(10) NOT NULL,
    procedure_code_type VARCHAR(10) DEFAULT 'CPT',  -- CPT, HCPCS, ICD10PCS
    -- Modifiers
    modifier_1 VARCHAR(2),
    modifier_2 VARCHAR(2),
    modifier_3 VARCHAR(2),
    modifier_4 VARCHAR(2),
    -- Service
    service_date DATE,
    service_date_end DATE,
    place_of_service VARCHAR(2),
    units DECIMAL(10,3) DEFAULT 1,
    unit_type VARCHAR(3) DEFAULT 'UN',
    -- Diagnosis pointer (1-based indices into claim diagnosis_codes)
    diagnosis_pointer JSONB DEFAULT '[1]',
    -- Financial
    line_charge DECIMAL(12,2) DEFAULT 0,
    allowed_amount DECIMAL(12,2),
    paid_amount DECIMAL(12,2),
    -- Institutional
    revenue_code VARCHAR(4),
    ndc_code VARCHAR(12),
    rendering_provider_npi VARCHAR(10),
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(claim_id, line_number)
);

-- =====================================================
-- SERVICE HISTORY TABLE
-- For frequency/duplicate detection
-- =====================================================
CREATE TABLE service_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_id VARCHAR(50) NOT NULL REFERENCES eligibility(member_id),
    procedure_code VARCHAR(10) NOT NULL,
    service_date DATE NOT NULL,
    provider_npi VARCHAR(10),
    quantity INTEGER DEFAULT 1,
    amount DECIMAL(12,2),
    claim_id VARCHAR(50) REFERENCES claims(claim_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- BENEFIT UTILIZATION TABLE
-- For tracking benefit usage
-- =====================================================
CREATE TABLE benefit_utilization (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_id VARCHAR(50) NOT NULL REFERENCES eligibility(member_id),
    procedure_code VARCHAR(10) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    units_used INTEGER DEFAULT 0,
    amount_used DECIMAL(12,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(member_id, procedure_code, period_start, period_end)
);
