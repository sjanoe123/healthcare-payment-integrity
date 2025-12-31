#!/usr/bin/env python3
"""
Healthcare Payment Integrity Test Data Generator

Generates 10K+ records with realistic fraud scenarios
aligned with the existing rules engine.

Usage:
    python seed_data.py [--connection-string <conn>] [--claims <count>]

Environment variables:
    DB_HOST: PostgreSQL host (default: localhost)
    DB_PORT: PostgreSQL port (default: 5433)
    DB_NAME: Database name (default: healthcare_claims)
    DB_USER: Database user (default: hpi_user)
    DB_PASSWORD: Database password (default: hpi_secure_password)
"""

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import execute_batch, Json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from reference_loader import ReferenceDataLoader
from fraud_scenarios import (
    FraudScenarioGenerator,
    FraudScenarioType,
    ClaimData,
    ClaimLine,
)
from utils import (
    generate_npi,
    generate_member_id,
    generate_claim_id,
    generate_line_id,
    generate_auth_number,
    random_date,
    random_dob,
    random_first_name,
    random_last_name,
    random_address,
    random_phone,
    random_email,
    random_diagnosis,
    random_taxonomy,
    get_specialty_description,
    random_plan,
    random_pos,
    calculate_age,
    TAXONOMY_CODES,
    US_STATES,
)


class DataSeeder:
    """Main data seeding orchestrator."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        total_claims: int = 10_000,
        total_members: int = 2_000,
        total_providers: int = 500,
    ):
        """
        Initialize the data seeder.

        Args:
            connection_string: PostgreSQL connection string
            total_claims: Number of claims to generate (default: 10,000)
            total_members: Number of members to generate (default: 2,000)
            total_providers: Number of providers to generate (default: 500)
        """
        self.conn_string = connection_string or self._build_connection_string()
        self.conn: Optional[psycopg2.connection] = None

        # Counts
        self.total_claims = total_claims
        self.total_members = total_members
        self.total_providers = total_providers

        # Reference data and fraud generator
        self.ref_loader: Optional[ReferenceDataLoader] = None
        self.fraud_gen: Optional[FraudScenarioGenerator] = None

        # Generated entities for cross-referencing
        self.providers: list[dict] = []
        self.members: list[dict] = []
        self.excluded_provider_npis: list[str] = []
        self.auth_required_codes: set[str] = set()

        # Track claim patterns for near-duplicate detection
        self.claim_patterns: dict[tuple, list[str]] = defaultdict(list)

    def _build_connection_string(self) -> str:
        """Build connection string from environment variables."""
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "5433")
        dbname = os.environ.get("DB_NAME", "healthcare_claims")
        user = os.environ.get("DB_USER", "hpi_user")
        password = os.environ.get("DB_PASSWORD", "hpi_secure_password")
        return f"host={host} port={port} dbname={dbname} user={user} password={password}"

    def connect(self, max_retries: int = 3, retry_delay: int = 5):
        """Connect to the database with retry logic for CI environments."""
        for attempt in range(max_retries):
            try:
                print(f"Connecting to database (attempt {attempt + 1}/{max_retries})...")
                self.conn = psycopg2.connect(self.conn_string)
                self.conn.autocommit = False
                print("Connected successfully")
                return
            except psycopg2.OperationalError as e:
                if attempt < max_retries - 1:
                    print(f"Connection failed: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    print(f"Connection failed after {max_retries} attempts")
                    raise

    def disconnect(self):
        """Disconnect from the database."""
        if self.conn:
            self.conn.close()
            self.conn = None
            print("Disconnected from database")

    def load_reference_data(self):
        """Load reference data for fraud scenario generation."""
        print("\nLoading reference data...")
        data_dir = Path(__file__).parent.parent.parent / "data"

        if not data_dir.exists():
            print(f"  WARNING: Reference data directory not found: {data_dir}")
            print("  Run 'make data-all' from the project root to download CMS data.")
            print("  Proceeding with limited fraud scenario generation...\n")

        self.ref_loader = ReferenceDataLoader(data_dir)
        self.ref_loader.load_all()

        self.fraud_gen = FraudScenarioGenerator(self.ref_loader)
        self.auth_required_codes = self.fraud_gen.auth_required_codes
        self.excluded_provider_npis = self.fraud_gen.oig_excluded_npis

    def seed_all(self):
        """Run the complete seeding process."""
        try:
            self.connect()
            self.load_reference_data()

            # Phase 1: Generate providers
            print(f"\n{'='*60}")
            print("Phase 1: Generating Providers")
            print('='*60)
            self._generate_providers()
            self._insert_providers()

            # Phase 2: Generate members and eligibility
            print(f"\n{'='*60}")
            print("Phase 2: Generating Members & Eligibility")
            print('='*60)
            self._generate_members()
            self._insert_members()

            # Phase 3: Generate supporting data
            print(f"\n{'='*60}")
            print("Phase 3: Generating Supporting Data")
            print('='*60)
            self._insert_auth_required_codes()
            self._insert_benefit_limits()
            self._insert_prior_authorizations()

            # Phase 4: Generate claims
            print(f"\n{'='*60}")
            print("Phase 4: Generating Claims")
            print('='*60)
            self._generate_and_insert_claims()

            # Phase 5: Generate provider history
            print(f"\n{'='*60}")
            print("Phase 5: Generating Provider History")
            print('='*60)
            self._generate_provider_history()

            self.conn.commit()
            print(f"\n{'='*60}")
            print("SEEDING COMPLETE")
            print('='*60)
            self._print_summary()

        except Exception as e:
            if self.conn:
                self.conn.rollback()
            raise e
        finally:
            self.disconnect()

    # =====================================================
    # PROVIDER GENERATION
    # =====================================================

    def _generate_providers(self):
        """Generate provider records."""
        print(f"Generating {self.total_providers} providers...")

        # Reserve 10% of providers for OIG-excluded NPIs, max 50
        max_oig = min(50, len(self.excluded_provider_npis))
        oig_count = min(max_oig, int(self.total_providers * 0.10))

        for i in range(self.total_providers):
            if i < oig_count:
                # Use actual OIG excluded NPI
                npi = self.excluded_provider_npis[i]
                is_excluded = True
            else:
                # Generate new NPI
                npi = generate_npi()
                # Ensure it's not accidentally in the exclusion list
                while self.ref_loader and self.ref_loader.is_oig_excluded(npi):
                    npi = generate_npi()
                is_excluded = False

            provider_type = "1" if random.random() < 0.85 else "2"  # 85% individual
            taxonomy = random_taxonomy()
            address = random_address()

            provider = {
                "npi": npi,
                "provider_type": provider_type,
                "first_name": random_first_name() if provider_type == "1" else None,
                "last_name": random_last_name() if provider_type == "1" else None,
                "organization_name": f"{random_last_name()} Medical Group" if provider_type == "2" else None,
                "credential": random.choice(["MD", "DO", "NP", "PA", "DPM"]) if provider_type == "1" else None,
                "primary_taxonomy": taxonomy,
                "specialty_description": get_specialty_description(taxonomy),
                "practice_address_line1": address["address_line1"],
                "practice_city": address["city"],
                "practice_state": address["state"],
                "practice_zip": address["zip_code"],
                "phone": random_phone(),
                "enumeration_date": random_date(2005, 2020),
                "last_update_date": random_date(2022, 2024),
                "is_oig_excluded": is_excluded,
                "exclusion_date": random_date(2020, 2024) if is_excluded else None,
                "exclusion_type": random.choice(["1128(a)(1)", "1128(a)(2)", "1128(b)(4)"]) if is_excluded else None,
                "is_fwa_watchlist": random.random() < 0.02 if not is_excluded else False,
                "avg_monthly_claims": random.randint(10, 200),
            }
            self.providers.append(provider)

        print(f"  Generated {len(self.providers)} providers ({oig_count} OIG-excluded)")

    def _insert_providers(self):
        """Insert providers into database."""
        print("Inserting providers...")

        sql = """
            INSERT INTO providers (
                npi, provider_type, first_name, last_name, organization_name,
                credential, primary_taxonomy, specialty_description,
                practice_address_line1, practice_city, practice_state, practice_zip,
                phone, enumeration_date, last_update_date,
                is_oig_excluded, exclusion_date, exclusion_type,
                is_fwa_watchlist, avg_monthly_claims
            ) VALUES (
                %(npi)s, %(provider_type)s, %(first_name)s, %(last_name)s, %(organization_name)s,
                %(credential)s, %(primary_taxonomy)s, %(specialty_description)s,
                %(practice_address_line1)s, %(practice_city)s, %(practice_state)s, %(practice_zip)s,
                %(phone)s, %(enumeration_date)s, %(last_update_date)s,
                %(is_oig_excluded)s, %(exclusion_date)s, %(exclusion_type)s,
                %(is_fwa_watchlist)s, %(avg_monthly_claims)s
            )
        """

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, self.providers, page_size=100)

        print(f"  Inserted {len(self.providers)} providers")

    # =====================================================
    # MEMBER GENERATION
    # =====================================================

    def _generate_members(self):
        """Generate member/eligibility records."""
        print(f"Generating {self.total_members} members...")

        # Get non-excluded providers for PCP assignment
        valid_providers = [p for p in self.providers if not p["is_oig_excluded"]]

        for i in range(self.total_members):
            member_id = generate_member_id(i + 1)
            first_name = random_first_name()
            last_name = random_last_name()
            dob = random_dob(18, 85)
            address = random_address()
            plan_id, plan_name, payer_id, payer_name = random_plan()

            # 80% have active PCP
            pcp_npi = None
            if valid_providers and random.random() < 0.80:
                pcp = random.choice(valid_providers)
                pcp_npi = pcp["npi"]

            # Effective date: random in past 1-5 years
            effective_date = random_date(2020, 2023)

            # 95% active, 5% terminated
            if random.random() < 0.95:
                status = "active"
                termination_date = None
            else:
                status = "terminated"
                termination_date = random_date(2023, 2024)

            member = {
                "member_id": member_id,
                "subscriber_id": member_id,  # Same as member for simplicity
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": dob,
                "gender": random.choice(["M", "F"]),
                "address_line1": address["address_line1"],
                "city": address["city"],
                "state": address["state"],
                "zip_code": address["zip_code"],
                "phone": random_phone(),
                "email": random_email(first_name, last_name),
                "status": status,
                "status_date": termination_date or effective_date,
                "plan_id": plan_id,
                "plan_name": plan_name,
                "group_number": f"GRP{random.randint(1000, 9999)}",
                "effective_date": effective_date,
                "termination_date": termination_date,
                "payer_id": payer_id,
                "payer_name": payer_name,
                "pcp_npi": pcp_npi,
                "cob_order": 1,
            }
            self.members.append(member)

        print(f"  Generated {len(self.members)} members")

    def _insert_members(self):
        """Insert members into database."""
        print("Inserting members...")

        sql = """
            INSERT INTO eligibility (
                member_id, subscriber_id, first_name, last_name, date_of_birth,
                gender, address_line1, city, state, zip_code, phone, email,
                status, status_date, plan_id, plan_name, group_number,
                effective_date, termination_date, payer_id, payer_name,
                pcp_npi, cob_order
            ) VALUES (
                %(member_id)s, %(subscriber_id)s, %(first_name)s, %(last_name)s, %(date_of_birth)s,
                %(gender)s, %(address_line1)s, %(city)s, %(state)s, %(zip_code)s, %(phone)s, %(email)s,
                %(status)s, %(status_date)s, %(plan_id)s, %(plan_name)s, %(group_number)s,
                %(effective_date)s, %(termination_date)s, %(payer_id)s, %(payer_name)s,
                %(pcp_npi)s, %(cob_order)s
            )
        """

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, self.members, page_size=100)

        print(f"  Inserted {len(self.members)} members")

    # =====================================================
    # SUPPORTING DATA
    # =====================================================

    def _insert_auth_required_codes(self):
        """Insert authorization-required procedure codes."""
        print("Inserting auth-required codes...")

        records = [
            {
                "procedure_code": code,
                "requires_auth": True,
                "auth_type": "prior",
                "description": f"Authorization required for {code}",
            }
            for code in self.auth_required_codes
        ]

        sql = """
            INSERT INTO auth_required_codes (procedure_code, requires_auth, auth_type, description)
            VALUES (%(procedure_code)s, %(requires_auth)s, %(auth_type)s, %(description)s)
            ON CONFLICT (procedure_code) DO NOTHING
        """

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, records, page_size=50)

        print(f"  Inserted {len(records)} auth-required codes")

    def _insert_benefit_limits(self):
        """Insert benefit limits for common procedures."""
        print("Inserting benefit limits...")

        # Get unique plan IDs
        plan_ids = list(set(m["plan_id"] for m in self.members))

        # Define limits for common procedure categories
        limit_definitions = [
            # Physical therapy (12 visits/year)
            ("97110", 12, 1200.00, "yearly"),
            ("97140", 12, 1200.00, "yearly"),
            # Mental health (30 visits/year)
            ("90834", 30, 4500.00, "yearly"),
            ("90837", 30, 6000.00, "yearly"),
            # Imaging limits
            ("70553", 2, 3000.00, "yearly"),  # MRI brain
            ("72148", 2, 3000.00, "yearly"),  # MRI lumbar
        ]

        records = []
        for plan_id in plan_ids:
            for code, max_units, max_amount, time_period in limit_definitions:
                records.append({
                    "plan_id": plan_id,
                    "procedure_code": code,
                    "max_units": max_units,
                    "max_amount": max_amount,
                    "time_period": time_period,
                })

        sql = """
            INSERT INTO benefit_limits (plan_id, procedure_code, max_units, max_amount, time_period)
            VALUES (%(plan_id)s, %(procedure_code)s, %(max_units)s, %(max_amount)s, %(time_period)s)
            ON CONFLICT (plan_id, procedure_code) DO NOTHING
        """

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, records, page_size=100)

        print(f"  Inserted {len(records)} benefit limits")

    def _insert_prior_authorizations(self):
        """Insert prior authorizations for some members."""
        print("Inserting prior authorizations...")

        records = []
        # 30% of members have at least one auth
        members_with_auth = random.sample(
            self.members,
            k=int(len(self.members) * 0.30)
        )

        for member in members_with_auth:
            # 1-3 authorizations per member
            num_auths = random.randint(1, 3)
            codes = random.sample(list(self.auth_required_codes), min(num_auths, len(self.auth_required_codes)))

            for code in codes:
                auth_date = random_date(2023, 2024)
                expiration_date = auth_date + timedelta(days=random.choice([90, 180, 365]))

                records.append({
                    "member_id": member["member_id"],
                    "procedure_code": code,
                    "auth_number": generate_auth_number(),
                    "status": random.choices(
                        ["approved", "expired", "denied"],
                        weights=[80, 15, 5]
                    )[0],
                    "auth_date": auth_date,
                    "expiration_date": expiration_date,
                    "approved_units": random.randint(1, 10),
                    "approved_amount": random.uniform(500, 5000),
                    "requesting_provider_npi": random.choice(self.providers)["npi"],
                })

        sql = """
            INSERT INTO prior_authorizations (
                member_id, procedure_code, auth_number, status,
                auth_date, expiration_date, approved_units, approved_amount,
                requesting_provider_npi
            ) VALUES (
                %(member_id)s, %(procedure_code)s, %(auth_number)s, %(status)s,
                %(auth_date)s, %(expiration_date)s, %(approved_units)s, %(approved_amount)s,
                %(requesting_provider_npi)s
            )
        """

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, records, page_size=100)

        print(f"  Inserted {len(records)} prior authorizations")

    # =====================================================
    # CLAIM GENERATION
    # =====================================================

    def _generate_and_insert_claims(self):
        """Generate and insert claims with fraud scenario distribution."""
        print(f"Generating {self.total_claims} claims...")

        # Get scenario distribution
        distribution = self.fraud_gen.get_scenario_distribution(self.total_claims)

        print("\nScenario distribution:")
        for scenario, count in distribution.items():
            print(f"  {scenario.value}: {count}")

        # Build ordered list of scenarios
        scenario_list = []
        for scenario, count in distribution.items():
            scenario_list.extend([scenario] * count)

        # Shuffle to distribute scenarios evenly
        random.shuffle(scenario_list)

        # Get valid (non-excluded) providers for clean claims
        valid_providers = [p for p in self.providers if not p["is_oig_excluded"]]
        excluded_providers = [p for p in self.providers if p["is_oig_excluded"]]

        # Get active members
        active_members = [m for m in self.members if m["status"] == "active"]

        # Generate claims in batches
        batch_size = 500
        claims_batch = []
        lines_batch = []
        claim_count = 0

        for i, scenario in enumerate(scenario_list):
            # Select member (some members get more claims)
            member = self._weighted_member_selection(active_members)

            # Select provider based on scenario
            if scenario == FraudScenarioType.OIG_EXCLUDED and excluded_providers:
                provider = random.choice(excluded_providers)
            else:
                provider = random.choice(valid_providers)

            # Generate claim
            service_date = random_date(2024, 2024)
            claim_id = generate_claim_id(i + 1, 2024)

            claim_data = ClaimData(
                claim_id=claim_id,
                member_id=member["member_id"],
                billing_provider_npi=provider["npi"],
                statement_from_date=service_date,
                claim_type=random.choice(["837P", "837I"]) if random.random() < 0.1 else "837P",
                place_of_service=random_pos(),
                diagnosis_codes=random_diagnosis(random.randint(1, 4)),
            )

            # Apply scenario
            claim_data = self._apply_scenario(claim_data, scenario, excluded_providers)
            claim_data.calculate_total()

            # Convert to database records
            claim_record = {
                "claim_id": claim_data.claim_id,
                "member_id": claim_data.member_id,
                "claim_type": claim_data.claim_type,
                "patient_control_number": f"PCN{random.randint(100000, 999999)}",
                "billing_provider_npi": claim_data.billing_provider_npi,
                "rendering_provider_npi": claim_data.billing_provider_npi,
                "facility_npi": None,
                "statement_from_date": claim_data.statement_from_date,
                "statement_to_date": claim_data.statement_from_date,
                "received_date": claim_data.statement_from_date + timedelta(days=random.randint(1, 14)),
                "place_of_service": claim_data.place_of_service,
                "principal_diagnosis": claim_data.diagnosis_codes[0] if claim_data.diagnosis_codes else None,
                "diagnosis_codes": Json(claim_data.diagnosis_codes),
                "total_charge": claim_data.total_charge,
                "total_allowed": claim_data.total_charge * random.uniform(0.6, 0.9),
                "total_paid": None,
                "payer_plan_period_id": member["plan_id"],
                "status": "pending",
            }
            claims_batch.append(claim_record)

            # Convert lines
            for line in claim_data.lines:
                line_record = {
                    "line_id": generate_line_id(claim_data.claim_id, line.line_number),
                    "claim_id": claim_data.claim_id,
                    "line_number": line.line_number,
                    "procedure_code": line.procedure_code,
                    "procedure_code_type": "HCPCS" if line.procedure_code[0].isalpha() else "CPT",
                    "modifier_1": line.modifier_1,
                    "modifier_2": line.modifier_2,
                    "service_date": line.service_date or claim_data.statement_from_date,
                    "place_of_service": line.place_of_service,
                    "units": line.units,
                    "diagnosis_pointer": Json(line.diagnosis_pointer),
                    "line_charge": line.line_charge,
                }
                lines_batch.append(line_record)

            claim_count += 1

            # Insert batch
            if len(claims_batch) >= batch_size:
                self._insert_claims_batch(claims_batch, lines_batch)
                print(f"  Inserted {claim_count} claims...")
                claims_batch = []
                lines_batch = []

        # Insert remaining
        if claims_batch:
            self._insert_claims_batch(claims_batch, lines_batch)

        print(f"  Total claims inserted: {claim_count}")

    def _weighted_member_selection(self, members: list[dict]) -> dict:
        """Select a member with some members getting more claims."""
        # 20% of members get 50% of claims (Pareto-like distribution)
        if random.random() < 0.50:
            # Select from top 20%
            top_members = members[:int(len(members) * 0.20)]
            return random.choice(top_members) if top_members else random.choice(members)
        return random.choice(members)

    def _apply_scenario(
        self,
        claim: ClaimData,
        scenario: FraudScenarioType,
        excluded_providers: list[dict],
    ) -> ClaimData:
        """Apply the appropriate fraud scenario to a claim."""
        excluded_npis = [p["npi"] for p in excluded_providers]

        if scenario == FraudScenarioType.OIG_EXCLUDED:
            return self.fraud_gen.create_oig_excluded_claim(claim, excluded_npis)
        elif scenario == FraudScenarioType.NCCI_PTP_VIOLATION:
            return self.fraud_gen.create_ncci_ptp_violation(claim)
        elif scenario == FraudScenarioType.NCCI_MUE_VIOLATION:
            return self.fraud_gen.create_ncci_mue_violation(claim)
        elif scenario == FraudScenarioType.FEE_SCHEDULE_OUTLIER:
            return self.fraud_gen.create_fee_schedule_outlier(claim)
        elif scenario == FraudScenarioType.MISSING_AUTHORIZATION:
            return self.fraud_gen.create_missing_auth_claim(claim)
        elif scenario == FraudScenarioType.POLICY_VIOLATION:
            return self.fraud_gen.create_policy_violation(claim)
        elif scenario == FraudScenarioType.BORDERLINE_FEE:
            return self.fraud_gen.create_borderline_fee(claim)
        elif scenario == FraudScenarioType.NEAR_MUE_LIMIT:
            return self.fraud_gen.create_near_mue_limit(claim)
        elif scenario == FraudScenarioType.CODING_ISSUE:
            return self.fraud_gen.create_coding_issue(claim)
        else:
            return self.fraud_gen.create_clean_claim(claim)

    def _insert_claims_batch(self, claims: list[dict], lines: list[dict]):
        """Insert a batch of claims and lines."""
        claims_sql = """
            INSERT INTO claims (
                claim_id, member_id, claim_type, patient_control_number,
                billing_provider_npi, rendering_provider_npi, facility_npi,
                statement_from_date, statement_to_date, received_date,
                place_of_service, principal_diagnosis, diagnosis_codes,
                total_charge, total_allowed, total_paid,
                payer_plan_period_id, status
            ) VALUES (
                %(claim_id)s, %(member_id)s, %(claim_type)s, %(patient_control_number)s,
                %(billing_provider_npi)s, %(rendering_provider_npi)s, %(facility_npi)s,
                %(statement_from_date)s, %(statement_to_date)s, %(received_date)s,
                %(place_of_service)s, %(principal_diagnosis)s, %(diagnosis_codes)s,
                %(total_charge)s, %(total_allowed)s, %(total_paid)s,
                %(payer_plan_period_id)s, %(status)s
            )
        """

        lines_sql = """
            INSERT INTO claim_lines (
                line_id, claim_id, line_number, procedure_code, procedure_code_type,
                modifier_1, modifier_2, service_date, place_of_service,
                units, diagnosis_pointer, line_charge
            ) VALUES (
                %(line_id)s, %(claim_id)s, %(line_number)s, %(procedure_code)s, %(procedure_code_type)s,
                %(modifier_1)s, %(modifier_2)s, %(service_date)s, %(place_of_service)s,
                %(units)s, %(diagnosis_pointer)s, %(line_charge)s
            )
        """

        with self.conn.cursor() as cur:
            execute_batch(cur, claims_sql, claims, page_size=100)
            execute_batch(cur, lines_sql, lines, page_size=200)

    # =====================================================
    # PROVIDER HISTORY
    # =====================================================

    def _generate_provider_history(self):
        """Generate provider history for volume analysis."""
        print("Generating provider history...")

        # Query claim counts by provider and month
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT
                    billing_provider_npi,
                    TO_CHAR(statement_from_date, 'YYYY-MM') as month_year,
                    COUNT(*) as claim_count,
                    SUM(total_charge) as total_billed,
                    COUNT(DISTINCT member_id) as unique_members
                FROM claims
                GROUP BY billing_provider_npi, TO_CHAR(statement_from_date, 'YYYY-MM')
            """)
            results = cur.fetchall()

        records = [
            {
                "npi": row[0],
                "month_year": row[1],
                "claim_count": row[2],
                "total_billed": float(row[3]) if row[3] else 0,
                "unique_members": row[4],
            }
            for row in results
        ]

        sql = """
            INSERT INTO provider_history (npi, month_year, claim_count, total_billed, unique_members)
            VALUES (%(npi)s, %(month_year)s, %(claim_count)s, %(total_billed)s, %(unique_members)s)
            ON CONFLICT (npi, month_year) DO UPDATE SET
                claim_count = EXCLUDED.claim_count,
                total_billed = EXCLUDED.total_billed,
                unique_members = EXCLUDED.unique_members
        """

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, records, page_size=100)

        print(f"  Inserted {len(records)} provider history records")

    # =====================================================
    # SUMMARY
    # =====================================================

    def _print_summary(self):
        """Print seeding summary."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM providers")
            provider_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM providers WHERE is_oig_excluded = TRUE")
            excluded_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM eligibility")
            member_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM claims")
            claim_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM claim_lines")
            line_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM prior_authorizations")
            auth_count = cur.fetchone()[0]

        print(f"\nDatabase Statistics:")
        print(f"  Providers: {provider_count} ({excluded_count} OIG-excluded)")
        print(f"  Members: {member_count}")
        print(f"  Claims: {claim_count}")
        print(f"  Claim Lines: {line_count}")
        print(f"  Prior Authorizations: {auth_count}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed healthcare payment integrity test database"
    )
    parser.add_argument(
        "--connection-string",
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--claims",
        type=int,
        default=10000,
        help="Number of claims to generate (default: 10000)",
    )
    parser.add_argument(
        "--members",
        type=int,
        default=2000,
        help="Number of members to generate (default: 2000)",
    )
    parser.add_argument(
        "--providers",
        type=int,
        default=500,
        help="Number of providers to generate (default: 500)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible test data generation",
    )

    args = parser.parse_args()

    # Validate and set random seed for reproducibility if provided
    if args.seed is not None:
        if args.seed < 0:
            parser.error("--seed must be a non-negative integer")
        random.seed(args.seed)
        print(f"Using random seed: {args.seed}")

    seeder = DataSeeder(
        connection_string=args.connection_string,
        total_claims=args.claims,
        total_members=args.members,
        total_providers=args.providers,
    )
    seeder.seed_all()


if __name__ == "__main__":
    main()
