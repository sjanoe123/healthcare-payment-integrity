-- =====================================================
-- Performance Indexes for Healthcare Payment Integrity
-- Optimized for fraud detection and connector sync queries
-- =====================================================

-- Provider lookups
CREATE INDEX idx_providers_oig_excluded ON providers(is_oig_excluded) WHERE is_oig_excluded = TRUE;
CREATE INDEX idx_providers_fwa_watchlist ON providers(is_fwa_watchlist) WHERE is_fwa_watchlist = TRUE;
CREATE INDEX idx_providers_taxonomy ON providers(primary_taxonomy);
CREATE INDEX idx_providers_state ON providers(practice_state);
CREATE INDEX idx_providers_updated ON providers(updated_at);

-- Provider history for volume analysis
CREATE INDEX idx_provider_history_npi ON provider_history(npi);
CREATE INDEX idx_provider_history_month ON provider_history(month_year);

-- Eligibility lookups
CREATE INDEX idx_eligibility_status ON eligibility(status);
CREATE INDEX idx_eligibility_dates ON eligibility(effective_date, termination_date);
CREATE INDEX idx_eligibility_plan ON eligibility(plan_id);
CREATE INDEX idx_eligibility_pcp ON eligibility(pcp_npi);
CREATE INDEX idx_eligibility_updated ON eligibility(updated_at);
CREATE INDEX idx_eligibility_dob ON eligibility(date_of_birth);

-- Claims lookups
CREATE INDEX idx_claims_member ON claims(member_id);
CREATE INDEX idx_claims_billing_provider ON claims(billing_provider_npi);
CREATE INDEX idx_claims_rendering_provider ON claims(rendering_provider_npi);
CREATE INDEX idx_claims_facility ON claims(facility_npi);
CREATE INDEX idx_claims_service_date ON claims(statement_from_date);
CREATE INDEX idx_claims_received_date ON claims(received_date);
CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_claims_type ON claims(claim_type);
CREATE INDEX idx_claims_updated ON claims(updated_at);
CREATE INDEX idx_claims_pos ON claims(place_of_service);

-- Claim lines - critical for NCCI and pricing rules
CREATE INDEX idx_claim_lines_claim ON claim_lines(claim_id);
CREATE INDEX idx_claim_lines_procedure ON claim_lines(procedure_code);
CREATE INDEX idx_claim_lines_service_date ON claim_lines(service_date);
CREATE INDEX idx_claim_lines_units ON claim_lines(units);
CREATE INDEX idx_claim_lines_revenue ON claim_lines(revenue_code);
CREATE INDEX idx_claim_lines_rendering ON claim_lines(rendering_provider_npi);

-- Prior auth lookups
CREATE INDEX idx_prior_auth_member ON prior_authorizations(member_id);
CREATE INDEX idx_prior_auth_code ON prior_authorizations(procedure_code);
CREATE INDEX idx_prior_auth_status ON prior_authorizations(status);
CREATE INDEX idx_prior_auth_dates ON prior_authorizations(auth_date, expiration_date);

-- Auth required codes
CREATE INDEX idx_auth_required_code ON auth_required_codes(procedure_code);

-- Benefit limits
CREATE INDEX idx_benefit_limits_plan ON benefit_limits(plan_id);
CREATE INDEX idx_benefit_limits_code ON benefit_limits(procedure_code);

-- Service history for frequency/duplicate detection
CREATE INDEX idx_service_history_member ON service_history(member_id);
CREATE INDEX idx_service_history_code ON service_history(procedure_code);
CREATE INDEX idx_service_history_date ON service_history(service_date);
CREATE INDEX idx_service_history_provider ON service_history(provider_npi);
CREATE INDEX idx_service_history_composite ON service_history(member_id, procedure_code, service_date);

-- Benefit utilization
CREATE INDEX idx_benefit_util_member ON benefit_utilization(member_id);
CREATE INDEX idx_benefit_util_code ON benefit_utilization(procedure_code);
CREATE INDEX idx_benefit_util_period ON benefit_utilization(period_start, period_end);

-- GIN index for JSONB diagnosis codes
CREATE INDEX idx_claims_diagnosis_gin ON claims USING GIN (diagnosis_codes);
CREATE INDEX idx_claim_lines_diag_pointer_gin ON claim_lines USING GIN (diagnosis_pointer);
