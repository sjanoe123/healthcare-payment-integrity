#!/usr/bin/env python3
"""
Kirk AI Test Data Generator

Generates comprehensive, denormalized claims for Kirk AI fraud detection testing.
Creates two tables:
- kirk_test: Claims for Kirk to analyze (no fraud hints)
- kirk_eval: Same claims with fraud labels for accuracy evaluation

All claims have the same comprehensive field structure.
"""

import argparse
import json
import os
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import psycopg2
from psycopg2.extras import execute_batch, Json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from reference_loader import ReferenceDataLoader
from utils import (
    generate_npi,
    generate_member_id,
    generate_claim_id,
    random_date,
    random_dob,
    random_first_name,
    random_last_name,
    random_address,
    random_phone,
    random_taxonomy,
    get_specialty_description,
    random_plan,
    US_STATES,
    TAXONOMY_CODES,
    DIAGNOSIS_CODES,
    PLACE_OF_SERVICE_CODES,
)

# =====================================================
# EXPANDED CONSTANTS FOR COMPREHENSIVE DATA
# =====================================================

# Revenue codes (UB-04)
REVENUE_CODES = {
    "0100": "All-Inclusive Room & Board",
    "0110": "Room & Board - Private",
    "0120": "Room & Board - Semi-Private",
    "0130": "Room & Board - Ward",
    "0150": "Room & Board - ICU",
    "0200": "Intensive Care",
    "0250": "Pharmacy",
    "0258": "IV Therapy Pharmacy",
    "0260": "IV Therapy",
    "0270": "Medical/Surgical Supplies",
    "0300": "Laboratory",
    "0301": "Chemistry",
    "0302": "Immunology",
    "0305": "Hematology",
    "0320": "Radiology - Diagnostic",
    "0324": "Radiology - CT Scan",
    "0350": "Operating Room",
    "0360": "Operating Room - Minor",
    "0370": "Anesthesia",
    "0380": "Blood",
    "0390": "Blood Storage",
    "0400": "Other Imaging",
    "0401": "MRI",
    "0410": "Respiratory Services",
    "0420": "Physical Therapy",
    "0430": "Occupational Therapy",
    "0440": "Speech Therapy",
    "0450": "Emergency Room",
    "0456": "Urgent Care",
    "0460": "Pulmonary Function",
    "0470": "Audiology",
    "0480": "Cardiology",
    "0490": "Ambulatory Surgery",
    "0500": "Outpatient Services",
    "0510": "Clinic",
    "0520": "Freestanding Clinic",
    "0530": "Osteopathic Services",
    "0540": "Ambulance",
    "0550": "Skilled Nursing",
    "0560": "Home Health - Medical Social Services",
    "0570": "Home Health - Aide",
    "0580": "Telemedicine",
    "0600": "Observation",
    "0610": "MRI - Brain",
    "0620": "MRI - Spine",
    "0636": "Drugs - Self-Administered",
    "0637": "Drugs - IV",
    "0700": "Cast Room",
    "0710": "Recovery Room",
    "0720": "Labor Room",
    "0730": "EKG/ECG",
    "0740": "EEG",
    "0750": "Gastro Services",
    "0760": "Specialty Treatment Room",
    "0770": "Preventive Care",
    "0780": "Telemedicine",
    "0790": "Extra-Corporeal Shock Wave Therapy",
    "0800": "Organ Acquisition",
    "0900": "Behavioral Health",
    "0901": "Psychiatric",
    "0902": "Day Treatment Psychiatric",
    "0910": "Psychiatric - Residential",
    "0940": "Other Therapeutic Services",
    "0942": "Cardiac Rehab",
    "0960": "Professional Fees",
    "0982": "Professional Fees - ER",
    "0983": "Professional Fees - Laboratory",
}

# Bill type codes
BILL_TYPE_CODES = {
    "0111": "Hospital Inpatient - Admit through Discharge",
    "0112": "Hospital Inpatient - First Interim Bill",
    "0113": "Hospital Inpatient - Continuing Claim",
    "0114": "Hospital Inpatient - Final Bill",
    "0117": "Hospital Inpatient - Replacement",
    "0121": "Hospital Inpatient Part B Only",
    "0131": "Hospital Outpatient",
    "0137": "Hospital Outpatient - Replacement",
    "0211": "SNF Inpatient Part A",
    "0212": "SNF Inpatient Part B",
    "0221": "SNF Inpatient Part A - First Interim",
    "0321": "Home Health Part A",
    "0322": "Home Health Part B",
    "0711": "Clinic - Rural Health",
    "0721": "Clinic - FQHC",
    "0731": "Clinic - ESRD",
    "0741": "Clinic - OPT",
    "0751": "Clinic - CORF",
    "0761": "Clinic - Community Mental Health",
    "0771": "Clinic - Federally Qualified Health Center",
    "0831": "Ambulatory Surgery Center",
    "0851": "Critical Access Hospital",
}

# Admission type codes
ADMISSION_TYPE_CODES = {
    "1": "Emergency",
    "2": "Urgent",
    "3": "Elective",
    "4": "Newborn",
    "5": "Trauma",
    "9": "Information Not Available",
}

# Admission source codes
ADMISSION_SOURCE_CODES = {
    "1": "Physician Referral",
    "2": "Clinic",
    "3": "HMO Referral",
    "4": "Transfer from Hospital",
    "5": "Transfer from SNF",
    "6": "Transfer from Another Facility",
    "7": "Emergency Room",
    "8": "Court/Law Enforcement",
    "9": "Information Not Available",
}

# Discharge status codes
DISCHARGE_STATUS_CODES = {
    "01": "Discharged to Home",
    "02": "Discharged to Short-term Hospital",
    "03": "Discharged to SNF",
    "04": "Discharged to ICF",
    "05": "Discharged to Another Institution",
    "06": "Discharged to Home with Home Health",
    "07": "Left Against Medical Advice",
    "09": "Admitted as Inpatient",
    "20": "Expired",
    "21": "Discharged to Court/Law",
    "30": "Still a Patient",
    "43": "Discharged to Federal Hospital",
    "50": "Hospice - Home",
    "51": "Hospice - Facility",
    "62": "Discharged to Inpatient Rehab",
    "63": "Discharged to Long-term Care Hospital",
    "65": "Discharged to Psychiatric Hospital",
    "66": "Discharged to Critical Access Hospital",
    "70": "Discharged to Another Type of Facility",
}

# Plan types
PLAN_TYPES = ["HMO", "PPO", "POS", "EPO", "Medicare", "Medicaid", "Medicare Advantage", "Medigap"]

# Unit types
UNIT_TYPES = ["UN", "F2", "MJ", "ML", "GR", "ME"]

# Condition codes (UB-04)
CONDITION_CODES = [
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "17", "18", "19", "20", "21", "25", "26", "27", "28",
    "29", "30", "31", "32", "33", "34", "35", "36", "37", "38",
    "40", "41", "42", "43", "44", "45", "46", "48", "55", "56",
    "57", "58", "59", "60", "61", "62", "66", "67", "68", "69",
]

# Occurrence codes (UB-04)
OCCURRENCE_CODES = [
    "01", "02", "03", "04", "05", "06", "09", "10", "11", "12",
    "17", "18", "19", "20", "21", "22", "24", "25", "26", "27",
    "28", "29", "30", "31", "32", "33", "34", "35", "36", "37",
]

# Provider credentials
CREDENTIALS = ["MD", "DO", "NP", "PA", "DPM", "DC", "OD", "DMD", "DDS", "PhD", "PsyD"]

# Procedure code descriptions (sample)
PROCEDURE_DESCRIPTIONS = {
    "99213": "Office Visit - Established Patient, Level 3",
    "99214": "Office Visit - Established Patient, Level 4",
    "99215": "Office Visit - Established Patient, Level 5",
    "99203": "Office Visit - New Patient, Level 3",
    "99204": "Office Visit - New Patient, Level 4",
    "99205": "Office Visit - New Patient, Level 5",
    "99212": "Office Visit - Established Patient, Level 2",
    "99211": "Office Visit - Established Patient, Level 1",
    "99221": "Initial Hospital Care, Level 1",
    "99222": "Initial Hospital Care, Level 2",
    "99223": "Initial Hospital Care, Level 3",
    "99231": "Subsequent Hospital Care, Level 1",
    "99232": "Subsequent Hospital Care, Level 2",
    "99233": "Subsequent Hospital Care, Level 3",
    "99281": "Emergency Department Visit, Level 1",
    "99282": "Emergency Department Visit, Level 2",
    "99283": "Emergency Department Visit, Level 3",
    "99284": "Emergency Department Visit, Level 4",
    "99285": "Emergency Department Visit, Level 5",
    "70553": "MRI Brain with/without Contrast",
    "72148": "MRI Lumbar Spine without Contrast",
    "74177": "CT Abdomen/Pelvis with Contrast",
    "93000": "Electrocardiogram (ECG)",
    "93306": "Echocardiogram Complete",
    "90834": "Psychotherapy, 45 minutes",
    "90837": "Psychotherapy, 60 minutes",
    "97110": "Therapeutic Exercises",
    "97140": "Manual Therapy",
    "36415": "Venipuncture",
    "85025": "Complete Blood Count (CBC)",
    "80053": "Comprehensive Metabolic Panel",
    "81001": "Urinalysis with Microscopy",
    "71046": "Chest X-Ray, 2 Views",
    "20610": "Arthrocentesis, Major Joint",
    "96372": "Injection, Therapeutic/Prophylactic",
    "J3301": "Triamcinolone Acetonide Injection",
    "J1100": "Dexamethasone Injection",
}

# Diagnosis descriptions (sample)
DIAGNOSIS_DESCRIPTIONS = {
    "J06.9": "Acute upper respiratory infection, unspecified",
    "J18.9": "Pneumonia, unspecified organism",
    "J20.9": "Acute bronchitis, unspecified",
    "M54.5": "Low back pain",
    "M25.50": "Pain in unspecified joint",
    "E11.9": "Type 2 diabetes mellitus without complications",
    "I10": "Essential (primary) hypertension",
    "E78.5": "Hyperlipidemia, unspecified",
    "I25.10": "Atherosclerotic heart disease of native coronary artery without angina",
    "F32.9": "Major depressive disorder, single episode, unspecified",
    "F41.1": "Generalized anxiety disorder",
    "G47.33": "Obstructive sleep apnea",
    "N39.0": "Urinary tract infection, site not specified",
    "K21.0": "Gastro-esophageal reflux disease with esophagitis",
    "J44.1": "Chronic obstructive pulmonary disease with acute exacerbation",
}


class KirkDataSeeder:
    """Generate comprehensive test data for Kirk AI evaluation."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        total_claims: int = 10_000,
    ):
        self.conn_string = connection_string or self._build_connection_string()
        self.conn: Optional[psycopg2.connection] = None
        self.total_claims = total_claims

        # Reference data
        self.ref_loader: Optional[ReferenceDataLoader] = None

        # Pre-generated entities
        self.providers: list[dict] = []
        self.members: list[dict] = []
        self.oig_excluded_npis: set[str] = set()

        # Fraud scenario tracking
        self.scenario_counts = {
            "oig_excluded": 0,
            "ncci_ptp_violation": 0,
            "ncci_mue_violation": 0,
            "fee_schedule_outlier": 0,
            "missing_authorization": 0,
            "policy_violation": 0,
            "borderline_fee": 0,
            "near_mue_limit": 0,
            "coding_issue": 0,
            "duplicate_pattern": 0,
            "clean": 0,
        }

    def _build_connection_string(self) -> str:
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "5433")
        dbname = os.environ.get("DB_NAME", "healthcare_claims")
        user = os.environ.get("DB_USER", "hpi_user")
        password = os.environ.get("DB_PASSWORD", "local_dev_only")
        return f"host={host} port={port} dbname={dbname} user={user} password={password}"

    def connect(self):
        print("Connecting to database...")
        self.conn = psycopg2.connect(self.conn_string)
        self.conn.autocommit = False
        print("Connected successfully")

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            print("Disconnected from database")

    def load_reference_data(self):
        print("\nLoading reference data...")
        data_dir = Path(__file__).parent.parent.parent / "data"
        self.ref_loader = ReferenceDataLoader(data_dir)
        self.ref_loader.load_all()

        # Get OIG excluded NPIs
        self.oig_excluded_npis = self.ref_loader.oig_exclusions
        print(f"  Loaded {len(self.oig_excluded_npis)} OIG excluded NPIs")

    def seed_all(self):
        try:
            self.connect()
            self.load_reference_data()

            # Create kirk tables
            print("\n" + "="*60)
            print("Creating Kirk test tables...")
            print("="*60)
            self._create_kirk_tables()

            # Generate providers and members (in memory)
            print("\n" + "="*60)
            print("Generating entities...")
            print("="*60)
            self._generate_providers(500)
            self._generate_members(2000)

            # Generate and insert claims
            print("\n" + "="*60)
            print(f"Generating {self.total_claims} comprehensive claims...")
            print("="*60)
            self._generate_and_insert_claims()

            self.conn.commit()
            print("\n" + "="*60)
            print("SEEDING COMPLETE")
            print("="*60)
            self._print_summary()

        except Exception as e:
            if self.conn:
                self.conn.rollback()
            raise e
        finally:
            self.disconnect()

    def _create_kirk_tables(self):
        """Create kirk_test and kirk_eval tables."""
        sql_file = Path(__file__).parent.parent / "init" / "03-kirk-tables.sql"
        with open(sql_file) as f:
            sql = f.read()

        with self.conn.cursor() as cur:
            cur.execute(sql)

        print("  Created kirk_test and kirk_eval tables")

    def _generate_providers(self, count: int):
        """Generate provider entities in memory."""
        print(f"  Generating {count} providers...")

        oig_list = list(self.oig_excluded_npis)[:50]
        oig_count = min(50, len(oig_list))

        for i in range(count):
            if i < oig_count:
                npi = oig_list[i]
                is_excluded = True
            else:
                npi = generate_npi()
                while npi in self.oig_excluded_npis:
                    npi = generate_npi()
                is_excluded = False

            taxonomy = random_taxonomy()
            address = random_address()
            first = random_first_name()
            last = random_last_name()

            self.providers.append({
                "npi": npi,
                "name": f"{first} {last}, {random.choice(CREDENTIALS)}",
                "first_name": first,
                "last_name": last,
                "taxonomy": taxonomy,
                "specialty": get_specialty_description(taxonomy),
                "credential": random.choice(CREDENTIALS),
                "address": address["address_line1"],
                "city": address["city"],
                "state": address["state"],
                "zip": address["zip_code"],
                "tax_id": f"{random.randint(10, 99)}-{random.randint(1000000, 9999999)}",
                "is_oig_excluded": is_excluded,
            })

        print(f"    Generated {len(self.providers)} providers ({oig_count} OIG-excluded)")

    def _generate_members(self, count: int):
        """Generate member entities in memory."""
        print(f"  Generating {count} members...")

        for i in range(count):
            member_id = generate_member_id(i + 1)
            first = random_first_name()
            last = random_last_name()
            dob = random_dob(18, 85)
            address = random_address()
            plan_id, plan_name, payer_id, payer_name = random_plan()

            self.members.append({
                "member_id": member_id,
                "subscriber_id": member_id,
                "first_name": first,
                "last_name": last,
                "dob": dob,
                "age": (date.today() - dob).days // 365,
                "gender": random.choice(["M", "F"]),
                "address": address["address_line1"],
                "city": address["city"],
                "state": address["state"],
                "zip": address["zip_code"],
                "group_number": f"GRP{random.randint(1000, 9999)}",
                "group_name": f"{random_last_name()} Corporation",
                "payer_id": payer_id,
                "payer_name": payer_name,
                "plan_id": plan_id,
                "plan_name": plan_name,
                "plan_type": random.choice(PLAN_TYPES),
            })

        print(f"    Generated {len(self.members)} members")

    def _generate_and_insert_claims(self):
        """Generate comprehensive claims and insert into both tables."""
        # Calculate scenario distribution
        distribution = self._get_scenario_distribution()
        print("\nScenario distribution:")
        for scenario, count in distribution.items():
            print(f"  {scenario}: {count}")

        # Build scenario list and shuffle
        scenario_list = []
        for scenario, count in distribution.items():
            scenario_list.extend([scenario] * count)
        random.shuffle(scenario_list)

        # Get valid and excluded providers
        valid_providers = [p for p in self.providers if not p["is_oig_excluded"]]
        excluded_providers = [p for p in self.providers if p["is_oig_excluded"]]

        # Generate claims in batches
        batch_size = 500
        kirk_test_batch = []
        kirk_eval_batch = []

        for i, scenario in enumerate(scenario_list):
            claim = self._generate_comprehensive_claim(
                i + 1,
                scenario,
                valid_providers,
                excluded_providers,
            )

            # Split into test (no fraud info) and eval (with fraud info)
            kirk_test_batch.append(self._to_kirk_test_record(claim))
            kirk_eval_batch.append(self._to_kirk_eval_record(claim, scenario))

            if len(kirk_test_batch) >= batch_size:
                self._insert_batch(kirk_test_batch, kirk_eval_batch)
                print(f"  Inserted {i + 1} claims...")
                kirk_test_batch = []
                kirk_eval_batch = []

        # Insert remaining
        if kirk_test_batch:
            self._insert_batch(kirk_test_batch, kirk_eval_batch)

        print(f"  Total claims inserted: {len(scenario_list)}")

    def _get_scenario_distribution(self) -> dict[str, int]:
        """Calculate claim distribution across scenarios."""
        high_risk = int(self.total_claims * 0.15)
        medium_risk = int(self.total_claims * 0.25)
        clean = self.total_claims - high_risk - medium_risk

        return {
            # High-risk (15%)
            "oig_excluded": int(high_risk * 0.20),
            "ncci_ptp_violation": int(high_risk * 0.20),
            "ncci_mue_violation": int(high_risk * 0.20),
            "fee_schedule_outlier": int(high_risk * 0.20),
            "missing_authorization": int(high_risk * 0.13),
            "policy_violation": high_risk - int(high_risk * 0.93),
            # Medium-risk (25%)
            "borderline_fee": int(medium_risk * 0.32),
            "near_mue_limit": int(medium_risk * 0.24),
            "coding_issue": int(medium_risk * 0.20),
            "duplicate_pattern": medium_risk - int(medium_risk * 0.76),
            # Clean (60%)
            "clean": clean,
        }

    def _generate_comprehensive_claim(
        self,
        index: int,
        scenario: str,
        valid_providers: list,
        excluded_providers: list,
    ) -> dict:
        """Generate a single comprehensive claim with all fields populated."""
        claim_id = generate_claim_id(index, 2024)
        member = random.choice(self.members)

        # Select provider based on scenario
        if scenario == "oig_excluded" and excluded_providers:
            billing_provider = random.choice(excluded_providers)
        else:
            billing_provider = random.choice(valid_providers)

        # Different rendering provider sometimes
        rendering_provider = billing_provider if random.random() < 0.7 else random.choice(valid_providers)
        referring_provider = random.choice(valid_providers) if random.random() < 0.3 else None

        # Dates
        service_date = random_date(2024, 2024)
        service_end_date = service_date + timedelta(days=random.randint(0, 3))

        # Claim type - mostly professional
        claim_type = "837I" if random.random() < 0.15 else "837P"
        is_institutional = claim_type == "837I"

        # Generate diagnoses (always populate multiple)
        num_diagnoses = random.randint(2, 8)
        diagnoses = random.sample(DIAGNOSIS_CODES, num_diagnoses)

        # Generate service lines (1-5)
        num_lines = random.choices([1, 2, 3, 4, 5], weights=[35, 30, 20, 10, 5])[0]
        lines = self._generate_service_lines(num_lines, scenario, service_date, diagnoses)

        # Financial calculations
        total_charge = sum(line["charge_amount"] for line in lines)
        total_allowed = total_charge * random.uniform(0.6, 0.85)
        copay = random.choice([0, 20, 25, 30, 40, 50])
        coinsurance = total_allowed * random.uniform(0.1, 0.3) if random.random() < 0.4 else 0
        deductible = random.choice([0, 0, 0, 100, 250, 500]) if random.random() < 0.3 else 0
        patient_resp = copay + coinsurance + deductible
        total_paid = max(0, total_allowed - patient_resp)

        # Place of service
        pos_code = self._select_pos_code(is_institutional)

        # Build comprehensive claim
        claim = {
            "claim_id": claim_id,
            "claim_control_number": f"CCN{random.randint(100000000, 999999999)}",
            "original_reference_number": f"ORN{random.randint(100000, 999999)}" if random.random() < 0.1 else None,
            "claim_type": claim_type,
            "claim_frequency_code": "1",
            "bill_type_code": random.choice(list(BILL_TYPE_CODES.keys())) if is_institutional else None,

            # Dates
            "statement_from_date": service_date,
            "statement_to_date": service_end_date,
            "admission_date": service_date if is_institutional else None,
            "discharge_date": service_end_date if is_institutional else None,
            "received_date": service_date + timedelta(days=random.randint(1, 14)),
            "paid_date": service_date + timedelta(days=random.randint(15, 45)) if random.random() < 0.8 else None,

            # Patient
            "member_id": member["member_id"],
            "patient_first_name": member["first_name"],
            "patient_last_name": member["last_name"],
            "patient_dob": member["dob"],
            "patient_age": member["age"],
            "patient_gender": member["gender"],
            "patient_address": member["address"],
            "patient_city": member["city"],
            "patient_state": member["state"],
            "patient_zip": member["zip"],
            "patient_relationship_to_subscriber": "18",

            # Subscriber
            "subscriber_id": member["subscriber_id"],
            "subscriber_first_name": member["first_name"],
            "subscriber_last_name": member["last_name"],
            "subscriber_dob": member["dob"],
            "subscriber_gender": member["gender"],
            "group_number": member["group_number"],
            "group_name": member["group_name"],

            # Payer
            "payer_id": member["payer_id"],
            "payer_name": member["payer_name"],
            "plan_id": member["plan_id"],
            "plan_name": member["plan_name"],
            "plan_type": member["plan_type"],
            "coverage_type": "Primary",

            # Billing Provider
            "billing_provider_npi": billing_provider["npi"],
            "billing_provider_name": billing_provider["name"],
            "billing_provider_taxonomy": billing_provider["taxonomy"],
            "billing_provider_specialty": billing_provider["specialty"],
            "billing_provider_address": billing_provider["address"],
            "billing_provider_city": billing_provider["city"],
            "billing_provider_state": billing_provider["state"],
            "billing_provider_zip": billing_provider["zip"],
            "billing_provider_tax_id": billing_provider["tax_id"],

            # Rendering Provider
            "rendering_provider_npi": rendering_provider["npi"],
            "rendering_provider_name": rendering_provider["name"],
            "rendering_provider_taxonomy": rendering_provider["taxonomy"],
            "rendering_provider_specialty": rendering_provider["specialty"],
            "rendering_provider_credential": rendering_provider["credential"],

            # Referring Provider
            "referring_provider_npi": referring_provider["npi"] if referring_provider else None,
            "referring_provider_name": referring_provider["name"] if referring_provider else None,

            # Facility
            "facility_npi": billing_provider["npi"] if is_institutional else None,
            "facility_name": f"{billing_provider['last_name']} Medical Center" if is_institutional else None,
            "facility_address": billing_provider["address"] if is_institutional else None,
            "facility_city": billing_provider["city"] if is_institutional else None,
            "facility_state": billing_provider["state"] if is_institutional else None,
            "facility_zip": billing_provider["zip"] if is_institutional else None,
            "facility_type": "Hospital" if is_institutional else None,

            # Place of Service
            "place_of_service_code": pos_code,
            "place_of_service_name": PLACE_OF_SERVICE_CODES.get(pos_code, "Other"),

            # Admission (Institutional)
            "admission_type_code": random.choice(list(ADMISSION_TYPE_CODES.keys())) if is_institutional else None,
            "admission_source_code": random.choice(list(ADMISSION_SOURCE_CODES.keys())) if is_institutional else None,
            "discharge_status_code": random.choice(["01", "02", "03", "06"]) if is_institutional else None,
            "patient_status_code": None,

            # DRG
            "drg_code": f"{random.randint(1, 999):03d}" if is_institutional and random.random() < 0.7 else None,
            "drg_description": "Medical DRG" if is_institutional else None,
            "drg_weight": round(random.uniform(0.5, 4.0), 4) if is_institutional else None,

            # Diagnoses
            "principal_diagnosis_code": diagnoses[0],
            "principal_diagnosis_description": DIAGNOSIS_DESCRIPTIONS.get(diagnoses[0], "Diagnosis"),
            "admitting_diagnosis_code": diagnoses[0] if is_institutional else None,
            "diagnosis_code_2": diagnoses[1] if len(diagnoses) > 1 else None,
            "diagnosis_code_3": diagnoses[2] if len(diagnoses) > 2 else None,
            "diagnosis_code_4": diagnoses[3] if len(diagnoses) > 3 else None,
            "diagnosis_code_5": diagnoses[4] if len(diagnoses) > 4 else None,
            "diagnosis_code_6": diagnoses[5] if len(diagnoses) > 5 else None,
            "diagnosis_code_7": diagnoses[6] if len(diagnoses) > 6 else None,
            "diagnosis_code_8": diagnoses[7] if len(diagnoses) > 7 else None,
            "diagnosis_code_9": None,
            "diagnosis_code_10": None,
            "diagnosis_code_11": None,
            "diagnosis_code_12": None,
            "diagnosis_present_on_admission": "Y" * min(len(diagnoses), 8),

            # External cause
            "external_cause_code_1": None,
            "external_cause_code_2": None,

            # Principal procedure (inpatient)
            "principal_procedure_code": None,
            "principal_procedure_date": None,
            "procedure_code_2": None,
            "procedure_date_2": None,
            "procedure_code_3": None,
            "procedure_date_3": None,

            # Service lines (denormalized)
            **self._flatten_service_lines(lines),

            # Financial
            "total_charge_amount": round(total_charge, 2),
            "total_allowed_amount": round(total_allowed, 2),
            "total_paid_amount": round(total_paid, 2),
            "patient_responsibility": round(patient_resp, 2),
            "copay_amount": copay,
            "coinsurance_amount": round(coinsurance, 2),
            "deductible_amount": deductible,

            # COB
            "other_payer_id": None,
            "other_payer_name": None,
            "other_payer_paid_amount": None,
            "cob_adjustment_amount": None,

            # Prior Auth
            "prior_auth_number": f"PA{random.randint(100000, 999999)}" if scenario != "missing_authorization" and random.random() < 0.3 else None,
            "prior_auth_status": "Approved" if random.random() < 0.9 else "Pending",
            "prior_auth_date": service_date - timedelta(days=random.randint(1, 30)) if random.random() < 0.3 else None,
            "prior_auth_expiration_date": service_date + timedelta(days=90) if random.random() < 0.3 else None,

            # Accident
            "accident_date": None,
            "accident_state": None,
            "accident_type": None,
            "last_menstrual_period": None,
            "disability_from_date": None,
            "disability_to_date": None,
            "hospitalization_from_date": service_date if is_institutional else None,
            "hospitalization_to_date": service_end_date if is_institutional else None,

            # Condition/Occurrence/Value codes
            "condition_codes": Json(random.sample(CONDITION_CODES, random.randint(0, 3))) if is_institutional else None,
            "occurrence_codes": Json([{"code": c, "date": str(service_date)} for c in random.sample(OCCURRENCE_CODES, random.randint(0, 2))]) if is_institutional else None,
            "value_codes": None,

            # Notes
            "claim_note": None,
            "attachment_control_number": None,

            # Line count
            "total_service_lines": num_lines,

            # Scenario metadata (for eval only)
            "_scenario": scenario,
            "_scenario_details": self._get_scenario_details(scenario, lines, billing_provider),
        }

        return claim

    def _generate_service_lines(
        self,
        count: int,
        scenario: str,
        service_date: date,
        diagnoses: list[str],
    ) -> list[dict]:
        """Generate service lines with scenario-specific modifications."""
        lines = []

        # Get reference data for scenarios
        ptp_pairs = list(self.ref_loader.ncci_ptp)[:500] if self.ref_loader else []
        mue_codes = list(self.ref_loader.ncci_mue.items())[:200] if self.ref_loader else []
        mpfs = self.ref_loader.mpfs if self.ref_loader else {}

        for i in range(count):
            # Select procedure code based on scenario
            if scenario == "ncci_ptp_violation" and i < 2 and ptp_pairs:
                ptp = random.choice(ptp_pairs)
                proc_code = ptp.column1 if i == 0 else ptp.column2
            elif scenario in ["ncci_mue_violation", "near_mue_limit"] and mue_codes:
                code, mue_entry = random.choice(mue_codes)
                proc_code = code
            else:
                proc_code = random.choice(list(PROCEDURE_DESCRIPTIONS.keys()))

            # Get pricing
            mpfs_entry = mpfs.get(proc_code)
            if mpfs_entry:
                base_rate = mpfs_entry.medicare_rate or random.uniform(50, 500)
            else:
                base_rate = random.uniform(50, 500)

            # Adjust charge based on scenario
            if scenario == "fee_schedule_outlier":
                charge = base_rate * random.uniform(2.5, 4.0)
            elif scenario == "borderline_fee":
                charge = base_rate * random.uniform(1.15, 1.45)
            else:
                charge = base_rate * random.uniform(0.9, 1.1)

            # Determine units based on scenario
            if scenario == "ncci_mue_violation" and mue_codes:
                code, mue_entry = random.choice(mue_codes)
                proc_code = code
                units = int(mue_entry.limit * random.uniform(1.5, 3.0))
            elif scenario == "near_mue_limit" and mue_codes:
                code, mue_entry = random.choice(mue_codes)
                proc_code = code
                units = mue_entry.limit
            else:
                units = random.choices([1, 2, 3, 4], weights=[70, 20, 7, 3])[0]

            # Revenue code for institutional
            rev_code = random.choice(list(REVENUE_CODES.keys()))

            line = {
                "procedure_code": proc_code,
                "procedure_description": PROCEDURE_DESCRIPTIONS.get(proc_code, "Healthcare Service"),
                "modifier_1": random.choice([None, "25", "59", "76", "77", "LT", "RT"]),
                "modifier_2": random.choice([None, None, None, "TC", "26"]),
                "modifier_3": None,
                "modifier_4": None,
                "revenue_code": rev_code,
                "revenue_description": REVENUE_CODES.get(rev_code, "Other"),
                "service_date": service_date,
                "service_date_end": service_date,
                "place_of_service": "11",
                "units": units,
                "unit_type": "UN",
                "charge_amount": round(charge * units, 2),
                "allowed_amount": round(charge * units * random.uniform(0.6, 0.85), 2),
                "ndc_code": None,
                "ndc_quantity": None,
                "ndc_unit": None,
                "diagnosis_pointer": ",".join(str(x) for x in range(1, min(len(diagnoses), 4) + 1)),
                "rendering_provider_npi": None,
            }
            lines.append(line)

        return lines

    def _flatten_service_lines(self, lines: list[dict]) -> dict:
        """Flatten service lines into line_1_*, line_2_*, etc. fields."""
        result = {}
        for i in range(5):  # Support up to 5 lines
            prefix = f"line_{i + 1}_"
            if i < len(lines):
                line = lines[i]
                for key, value in line.items():
                    result[prefix + key] = value
            else:
                # Fill with None for consistency
                for key in lines[0].keys() if lines else []:
                    result[prefix + key] = None
        return result

    def _select_pos_code(self, is_institutional: bool) -> str:
        """Select appropriate place of service code."""
        if is_institutional:
            return random.choice(["21", "22", "23", "31"])
        else:
            weights = [40, 15, 10, 8, 8, 5, 5, 5, 2, 2]
            codes = ["11", "22", "23", "21", "24", "12", "81", "31", "41", "49"]
            return random.choices(codes, weights=weights)[0]

    def _get_scenario_details(self, scenario: str, lines: list, provider: dict) -> dict:
        """Get scenario-specific details for evaluation."""
        details = {"scenario_type": scenario}

        if scenario == "oig_excluded":
            details["excluded_npi"] = provider["npi"]
            details["expected_rules"] = ["OIG_EXCLUSION"]
        elif scenario == "ncci_ptp_violation":
            if len(lines) >= 2:
                details["code_pair"] = [lines[0]["procedure_code"], lines[1]["procedure_code"]]
            details["expected_rules"] = ["NCCI_PTP"]
        elif scenario == "ncci_mue_violation":
            details["expected_rules"] = ["NCCI_MUE"]
        elif scenario == "fee_schedule_outlier":
            details["expected_rules"] = ["PRICING_EXCEEDS_FEE"]
        elif scenario == "missing_authorization":
            details["expected_rules"] = ["ELIGIBILITY_NO_AUTH"]

        return details

    def _to_kirk_test_record(self, claim: dict) -> dict:
        """Convert claim to kirk_test record (no fraud hints)."""
        record = {k: v for k, v in claim.items() if not k.startswith("_")}
        return record

    def _to_kirk_eval_record(self, claim: dict, scenario: str) -> dict:
        """Convert claim to kirk_eval record (with fraud labels)."""
        record = {k: v for k, v in claim.items() if not k.startswith("_")}

        # Add fraud evaluation fields
        record["fraud_scenario_type"] = scenario
        record["fraud_risk_level"] = self._get_risk_level(scenario)
        record["expected_rule_triggers"] = Json(claim.get("_scenario_details", {}).get("expected_rules", []))
        record["scenario_details"] = Json(claim.get("_scenario_details", {}))
        record["ground_truth_fraud_score"] = self._get_expected_fraud_score(scenario)

        return record

    def _get_risk_level(self, scenario: str) -> str:
        if scenario in ["oig_excluded", "ncci_ptp_violation", "ncci_mue_violation", "fee_schedule_outlier", "missing_authorization", "policy_violation"]:
            return "high"
        elif scenario in ["borderline_fee", "near_mue_limit", "coding_issue", "duplicate_pattern"]:
            return "medium"
        else:
            return "clean"

    def _get_expected_fraud_score(self, scenario: str) -> float:
        scores = {
            "oig_excluded": 0.95,
            "ncci_ptp_violation": 0.85,
            "ncci_mue_violation": 0.80,
            "fee_schedule_outlier": 0.75,
            "missing_authorization": 0.70,
            "policy_violation": 0.65,
            "borderline_fee": 0.45,
            "near_mue_limit": 0.40,
            "coding_issue": 0.35,
            "duplicate_pattern": 0.50,
            "clean": 0.10,
        }
        return scores.get(scenario, 0.10)

    def _insert_batch(self, test_batch: list, eval_batch: list):
        """Insert batches into both tables."""
        # Get column names from first record
        if not test_batch:
            return

        test_columns = [k for k in test_batch[0].keys()]
        eval_columns = [k for k in eval_batch[0].keys()]

        test_sql = f"""
            INSERT INTO kirk_test ({', '.join(test_columns)})
            VALUES ({', '.join(['%(' + c + ')s' for c in test_columns])})
        """

        eval_sql = f"""
            INSERT INTO kirk_eval ({', '.join(eval_columns)})
            VALUES ({', '.join(['%(' + c + ')s' for c in eval_columns])})
        """

        with self.conn.cursor() as cur:
            execute_batch(cur, test_sql, test_batch, page_size=100)
            execute_batch(cur, eval_sql, eval_batch, page_size=100)

    def _print_summary(self):
        """Print summary statistics."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM kirk_test")
            test_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM kirk_eval")
            eval_count = cur.fetchone()[0]

            cur.execute("""
                SELECT fraud_risk_level, COUNT(*)
                FROM kirk_eval
                GROUP BY fraud_risk_level
            """)
            risk_dist = dict(cur.fetchall())

            cur.execute("""
                SELECT fraud_scenario_type, COUNT(*)
                FROM kirk_eval
                GROUP BY fraud_scenario_type
                ORDER BY COUNT(*) DESC
            """)
            scenario_dist = cur.fetchall()

        print(f"\nKirk Test Tables Summary:")
        print(f"  kirk_test: {test_count} claims")
        print(f"  kirk_eval: {eval_count} claims")
        print(f"\nRisk Distribution:")
        for level, count in risk_dist.items():
            print(f"  {level}: {count}")
        print(f"\nScenario Distribution:")
        for scenario, count in scenario_dist:
            print(f"  {scenario}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Seed Kirk AI test tables")
    parser.add_argument("--claims", type=int, default=10000, help="Number of claims")
    parser.add_argument("--connection-string", help="PostgreSQL connection string")

    args = parser.parse_args()

    seeder = KirkDataSeeder(
        connection_string=args.connection_string,
        total_claims=args.claims,
    )
    seeder.seed_all()


if __name__ == "__main__":
    main()
