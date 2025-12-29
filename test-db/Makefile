.PHONY: up down seed reset logs shell test-connection setup clean help stats

# Default target
help:
	@echo "Healthcare Payment Integrity Test Database"
	@echo ""
	@echo "Usage:"
	@echo "  make setup          - Start database and seed with test data"
	@echo "  make up             - Start PostgreSQL container"
	@echo "  make down           - Stop PostgreSQL container"
	@echo "  make seed           - Seed database with 10K records"
	@echo "  make reset          - Drop and recreate database with fresh data"
	@echo "  make logs           - View PostgreSQL logs"
	@echo "  make shell          - Open psql shell"
	@echo "  make test-connection - Test database connection"
	@echo "  make stats          - Show database statistics"
	@echo "  make clean          - Remove all containers and volumes"
	@echo ""
	@echo "Connection details:"
	@echo "  Host: localhost"
	@echo "  Port: 5433"
	@echo "  Database: healthcare_claims"
	@echo "  User: hpi_user"
	@echo "  Password: hpi_secure_password"

# Docker commands
up:
	@echo "Starting PostgreSQL container..."
	docker-compose up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 5
	@docker-compose exec -T postgres pg_isready -U hpi_user -d healthcare_claims || (echo "Database not ready, waiting more..." && sleep 5)
	@echo "PostgreSQL is ready!"

down:
	@echo "Stopping PostgreSQL container..."
	docker-compose down

# Full reset - drop volumes and recreate
reset:
	@echo "Resetting database..."
	docker-compose down -v
	docker-compose up -d
	@echo "Waiting for PostgreSQL to initialize..."
	@sleep 8
	@docker-compose exec -T postgres pg_isready -U hpi_user -d healthcare_claims || (echo "Database not ready, waiting more..." && sleep 5)
	@echo "Database reset complete. Run 'make seed' to populate with test data."

# Seeding
seed:
	@echo "Seeding database with test data..."
	@echo "This will generate 10,000 claims, 2,000 members, and 500 providers..."
	cd seed && python seed_data.py
	@echo "Seeding complete!"

# Quick seed with fewer records (for testing)
seed-small:
	@echo "Seeding database with small dataset..."
	cd seed && python seed_data.py --claims 1000 --members 200 --providers 50

# Full setup - start and seed
setup: up seed
	@echo ""
	@echo "=========================================="
	@echo "Test database ready!"
	@echo "=========================================="
	@echo ""
	@echo "Connection string:"
	@echo "  postgresql://hpi_user:hpi_secure_password@localhost:5433/healthcare_claims"
	@echo ""
	@echo "To connect via psql:"
	@echo "  make shell"
	@echo ""

# Utilities
logs:
	docker-compose logs -f postgres

shell:
	docker-compose exec postgres psql -U hpi_user -d healthcare_claims

test-connection:
	@echo "Testing database connection..."
	@docker-compose exec -T postgres psql -U hpi_user -d healthcare_claims -c "SELECT 'Connection successful!' as status;"

# Show database statistics
stats:
	@echo "Database Statistics:"
	@echo "===================="
	@docker-compose exec -T postgres psql -U hpi_user -d healthcare_claims -c "\
		SELECT 'providers' as table_name, COUNT(*) as count FROM providers \
		UNION ALL \
		SELECT 'providers (OIG excluded)', COUNT(*) FROM providers WHERE is_oig_excluded = TRUE \
		UNION ALL \
		SELECT 'eligibility', COUNT(*) FROM eligibility \
		UNION ALL \
		SELECT 'claims', COUNT(*) FROM claims \
		UNION ALL \
		SELECT 'claim_lines', COUNT(*) FROM claim_lines \
		UNION ALL \
		SELECT 'prior_authorizations', COUNT(*) FROM prior_authorizations \
		UNION ALL \
		SELECT 'benefit_limits', COUNT(*) FROM benefit_limits \
		ORDER BY table_name;"

# Clean up everything
clean:
	@echo "Removing all containers and volumes..."
	docker-compose down -v --remove-orphans
	@echo "Cleanup complete."

# Kirk AI test tables
seed-kirk:
	@echo "Seeding Kirk AI test tables with comprehensive claims..."
	cd seed && python seed_kirk_tables.py
	@echo "Kirk tables seeded!"

seed-kirk-small:
	@echo "Seeding Kirk AI test tables (small dataset)..."
	cd seed && python seed_kirk_tables.py --claims 1000

kirk-stats:
	@echo "Kirk Test Tables Statistics:"
	@docker-compose exec -T postgres psql -U hpi_user -d healthcare_claims -c "\
		SELECT 'kirk_test' as table_name, COUNT(*) as count FROM kirk_test \
		UNION ALL \
		SELECT 'kirk_eval', COUNT(*) FROM kirk_eval;"
	@echo ""
	@echo "Risk Distribution (kirk_eval):"
	@docker-compose exec -T postgres psql -U hpi_user -d healthcare_claims -c "\
		SELECT fraud_risk_level, COUNT(*) \
		FROM kirk_eval \
		GROUP BY fraud_risk_level \
		ORDER BY COUNT(*) DESC;"
	@echo ""
	@echo "Scenario Distribution (kirk_eval):"
	@docker-compose exec -T postgres psql -U hpi_user -d healthcare_claims -c "\
		SELECT fraud_scenario_type, COUNT(*) \
		FROM kirk_eval \
		GROUP BY fraud_scenario_type \
		ORDER BY COUNT(*) DESC;"

kirk-sample:
	@echo "Sample claims from kirk_test (what Kirk sees):"
	@docker-compose exec -T postgres psql -U hpi_user -d healthcare_claims -c "\
		SELECT claim_id, patient_last_name, billing_provider_npi, \
		       billing_provider_specialty, total_charge_amount, \
		       line_1_procedure_code, line_1_units \
		FROM kirk_test \
		LIMIT 5;"

kirk-eval-sample:
	@echo "Sample claims from kirk_eval (with labels):"
	@docker-compose exec -T postgres psql -U hpi_user -d healthcare_claims -c "\
		SELECT claim_id, fraud_scenario_type, fraud_risk_level, \
		       ground_truth_fraud_score, total_charge_amount \
		FROM kirk_eval \
		LIMIT 10;"

# Sample queries for testing fraud detection
sample-oig:
	@echo "Claims from OIG-excluded providers:"
	@docker-compose exec -T postgres psql -U hpi_user -d healthcare_claims -c "\
		SELECT c.claim_id, c.billing_provider_npi, p.specialty_description, c.total_charge \
		FROM claims c \
		JOIN providers p ON c.billing_provider_npi = p.npi \
		WHERE p.is_oig_excluded = TRUE \
		LIMIT 10;"

sample-claims:
	@echo "Sample claims with lines:"
	@docker-compose exec -T postgres psql -U hpi_user -d healthcare_claims -c "\
		SELECT c.claim_id, c.member_id, c.billing_provider_npi, \
		       c.statement_from_date, c.total_charge, \
		       COUNT(cl.line_id) as line_count \
		FROM claims c \
		JOIN claim_lines cl ON c.claim_id = cl.claim_id \
		GROUP BY c.claim_id, c.member_id, c.billing_provider_npi, \
		         c.statement_from_date, c.total_charge \
		ORDER BY c.total_charge DESC \
		LIMIT 10;"
