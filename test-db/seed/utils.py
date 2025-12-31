"""
Utility functions for generating realistic healthcare test data.
"""

import random
import string
from datetime import date, timedelta
from typing import Optional

# =====================================================
# CONSTANTS
# =====================================================

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
]

FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Barbara", "David", "Elizabeth", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Edward", "Deborah", "Ronald", "Stephanie", "Timothy", "Rebecca", "Jason", "Sharon"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell"
]

CITY_NAMES = [
    "Springfield", "Franklin", "Clinton", "Madison", "Georgetown", "Salem", "Bristol",
    "Fairview", "Manchester", "Oxford", "Burlington", "Ashland", "Greenville", "Auburn",
    "Milton", "Newport", "Hudson", "Kingston", "Arlington", "Chester", "Marion"
]

STREET_NAMES = [
    "Main", "Oak", "Maple", "Cedar", "Pine", "Elm", "Washington", "Park", "Lake",
    "Hill", "Forest", "River", "Spring", "Church", "Market", "Union", "School"
]

STREET_SUFFIXES = ["St", "Ave", "Blvd", "Dr", "Ln", "Rd", "Way", "Ct", "Pl"]

# Provider taxonomy codes (subset of common ones)
TAXONOMY_CODES = [
    "207Q00000X",  # Family Medicine
    "207R00000X",  # Internal Medicine
    "207RC0000X",  # Cardiovascular Disease
    "207RE0101X",  # Endocrinology
    "207RG0100X",  # Gastroenterology
    "207RH0000X",  # Hematology
    "207RI0200X",  # Infectious Disease
    "207RN0300X",  # Nephrology
    "207RP1001X",  # Pulmonary Disease
    "207RR0500X",  # Rheumatology
    "208000000X",  # Pediatrics
    "2084P0800X",  # Psychiatry
    "208600000X",  # Surgery
    "207T00000X",  # Neurology
    "207X00000X",  # Orthopaedic Surgery
    "207Y00000X",  # Otolaryngology
    "208100000X",  # Physical Medicine
    "2082S0099X",  # Surgical Oncology
    "2083P0500X",  # Preventive Medicine
    "208VP0000X",  # Pain Medicine
    "363L00000X",  # Nurse Practitioner
    "363A00000X",  # Physician Assistant
    "332B00000X",  # Durable Medical Equipment
    "261QR0400X",  # Rehabilitation Center
    "261QU0200X",  # Urgent Care Center
]

SPECIALTY_DESCRIPTIONS = {
    "207Q00000X": "Family Medicine",
    "207R00000X": "Internal Medicine",
    "207RC0000X": "Cardiovascular Disease",
    "207RE0101X": "Endocrinology, Diabetes & Metabolism",
    "207RG0100X": "Gastroenterology",
    "207RH0000X": "Hematology",
    "207RI0200X": "Infectious Disease",
    "207RN0300X": "Nephrology",
    "207RP1001X": "Pulmonary Disease",
    "207RR0500X": "Rheumatology",
    "208000000X": "Pediatrics",
    "2084P0800X": "Psychiatry",
    "208600000X": "Surgery",
    "207T00000X": "Neurology",
    "207X00000X": "Orthopaedic Surgery",
    "207Y00000X": "Otolaryngology",
    "208100000X": "Physical Medicine & Rehabilitation",
    "2082S0099X": "Surgical Oncology",
    "2083P0500X": "Preventive Medicine",
    "208VP0000X": "Pain Medicine",
    "363L00000X": "Nurse Practitioner",
    "363A00000X": "Physician Assistant",
    "332B00000X": "Durable Medical Equipment",
    "261QR0400X": "Rehabilitation Center",
    "261QU0200X": "Urgent Care Center",
}

PLAN_NAMES = [
    "Blue Cross PPO Gold",
    "Blue Cross PPO Silver",
    "Blue Cross HMO",
    "Aetna Choice POS II",
    "Aetna Open Access HMO",
    "UnitedHealthcare Choice Plus",
    "UnitedHealthcare Navigate",
    "Cigna Connect",
    "Cigna Open Access Plus",
    "Humana Gold Plus HMO",
    "Kaiser Permanente HMO",
    "Anthem Blue Cross PPO",
    "Molina Healthcare",
    "Centene Ambetter",
    "Oscar Health PPO",
]

PAYER_NAMES = [
    "Blue Cross Blue Shield",
    "Aetna",
    "UnitedHealthcare",
    "Cigna",
    "Humana",
    "Kaiser Permanente",
    "Anthem",
    "Molina Healthcare",
    "Centene",
    "Oscar Health",
]

# Common ICD-10 diagnosis codes
DIAGNOSIS_CODES = [
    "J06.9",   # Acute upper respiratory infection
    "J18.9",   # Pneumonia, unspecified
    "J20.9",   # Acute bronchitis
    "J40",     # Bronchitis
    "J44.1",   # COPD with acute exacerbation
    "M54.5",   # Low back pain
    "M25.50",  # Joint pain
    "M79.3",   # Panniculitis
    "K21.0",   # GERD with esophagitis
    "K29.70",  # Gastritis
    "E11.9",   # Type 2 diabetes without complications
    "E11.65",  # Type 2 diabetes with hyperglycemia
    "E78.5",   # Hyperlipidemia
    "I10",     # Essential hypertension
    "I25.10",  # Atherosclerotic heart disease
    "I48.91",  # Atrial fibrillation
    "I50.9",   # Heart failure
    "N39.0",   # Urinary tract infection
    "N18.3",   # Chronic kidney disease, stage 3
    "R10.9",   # Abdominal pain
    "R05.9",   # Cough
    "R50.9",   # Fever
    "G43.909", # Migraine
    "G47.33",  # Obstructive sleep apnea
    "F32.9",   # Major depressive disorder
    "F41.1",   # Generalized anxiety disorder
    "Z23",     # Immunization encounter
    "Z00.00",  # General adult medical exam
    "Z12.31",  # Screening mammogram
    "Z12.11",  # Screening colonoscopy
]

# Place of service codes
PLACE_OF_SERVICE_CODES = {
    "11": "Office",
    "12": "Home",
    "19": "Off Campus-Outpatient Hospital",
    "21": "Inpatient Hospital",
    "22": "On Campus-Outpatient Hospital",
    "23": "Emergency Room - Hospital",
    "24": "Ambulatory Surgical Center",
    "31": "Skilled Nursing Facility",
    "32": "Nursing Facility",
    "41": "Ambulance - Land",
    "42": "Ambulance - Air/Water",
    "49": "Independent Clinic",
    "50": "Federally Qualified Health Center",
    "51": "Inpatient Psychiatric Facility",
    "52": "Psychiatric Facility-Partial Hospitalization",
    "53": "Community Mental Health Center",
    "61": "Comprehensive Inpatient Rehabilitation",
    "62": "Comprehensive Outpatient Rehabilitation",
    "65": "End-Stage Renal Disease Treatment Facility",
    "71": "Public Health Clinic",
    "72": "Rural Health Clinic",
    "81": "Independent Laboratory",
    "99": "Other Place of Service",
}

# =====================================================
# GENERATOR FUNCTIONS
# =====================================================


def generate_npi() -> str:
    """Generate a valid 10-digit NPI (National Provider Identifier)."""
    # NPIs start with 1 or 2 and are 10 digits
    prefix = random.choice(["1", "2"])
    remaining = "".join(random.choices(string.digits, k=9))
    return prefix + remaining


def generate_member_id(index: int) -> str:
    """Generate a unique member ID."""
    return f"MEM{index:08d}"


def generate_claim_id(index: int, year: int = 2024) -> str:
    """Generate a unique claim ID."""
    return f"CLM-{year}-{index:06d}"


def generate_line_id(claim_id: str, line_number: int) -> str:
    """Generate a unique line ID."""
    return f"{claim_id}-L{line_number:02d}"


def generate_auth_number() -> str:
    """Generate an authorization number."""
    return f"AUTH{random.randint(100000, 999999)}"


def random_date(
    start_year: int = 2023,
    end_year: int = 2024,
    start_month: int = 1,
    end_month: int = 12,
) -> date:
    """Generate a random date within the specified range."""
    start = date(start_year, start_month, 1)
    end = date(end_year, end_month, 28)
    days_between = (end - start).days
    random_days = random.randint(0, max(0, days_between))
    return start + timedelta(days=random_days)


def random_dob(min_age: int = 18, max_age: int = 85) -> date:
    """Generate a random date of birth for specified age range."""
    today = date.today()
    age = random.randint(min_age, max_age)
    birth_year = today.year - age
    return date(birth_year, random.randint(1, 12), random.randint(1, 28))


def random_first_name() -> str:
    """Generate a random first name."""
    return random.choice(FIRST_NAMES)


def random_last_name() -> str:
    """Generate a random last name."""
    return random.choice(LAST_NAMES)


def random_address() -> dict:
    """Generate a random address."""
    state = random.choice(US_STATES)
    return {
        "address_line1": f"{random.randint(100, 9999)} {random.choice(STREET_NAMES)} {random.choice(STREET_SUFFIXES)}",
        "city": random.choice(CITY_NAMES),
        "state": state,
        "zip_code": f"{random.randint(10000, 99999)}",
    }


def random_phone() -> str:
    """Generate a random phone number."""
    return f"{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}"


def random_email(first_name: str, last_name: str) -> str:
    """Generate an email address."""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "aol.com", "icloud.com"]
    return f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 99)}@{random.choice(domains)}"


def random_diagnosis(count: int = 1) -> list[str]:
    """Generate random diagnosis codes."""
    return random.sample(DIAGNOSIS_CODES, min(count, len(DIAGNOSIS_CODES)))


def random_taxonomy() -> str:
    """Generate a random provider taxonomy code."""
    return random.choice(TAXONOMY_CODES)


def get_specialty_description(taxonomy: str) -> str:
    """Get the specialty description for a taxonomy code."""
    return SPECIALTY_DESCRIPTIONS.get(taxonomy, "Other Specialty")


def random_plan() -> tuple[str, str, str, str]:
    """Generate random plan information: (plan_id, plan_name, payer_id, payer_name)."""
    payer_name = random.choice(PAYER_NAMES)
    plan_name = random.choice(PLAN_NAMES)
    payer_id = f"PYR{PAYER_NAMES.index(payer_name):03d}"
    plan_id = f"PLN{random.randint(1000, 9999)}"
    return plan_id, plan_name, payer_id, payer_name


def random_pos() -> str:
    """Generate a random place of service code."""
    # Weight towards common POS codes
    weights = {
        "11": 40,  # Office (most common)
        "22": 15,  # Outpatient Hospital
        "23": 10,  # Emergency Room
        "21": 8,   # Inpatient
        "24": 8,   # ASC
        "12": 5,   # Home
        "81": 5,   # Lab
        "31": 3,   # SNF
        "41": 2,   # Ambulance
        "49": 2,   # Clinic
        "65": 2,   # ESRD
    }
    codes = list(weights.keys())
    probs = [weights[c] / sum(weights.values()) for c in codes]
    return random.choices(codes, weights=probs, k=1)[0]


def calculate_age(dob: date, reference_date: Optional[date] = None) -> int:
    """Calculate age from date of birth."""
    if reference_date is None:
        reference_date = date.today()
    age = reference_date.year - dob.year
    if reference_date.month < dob.month or (
        reference_date.month == dob.month and reference_date.day < dob.day
    ):
        age -= 1
    return age


def weighted_choice(choices: list, weights: list):
    """Make a weighted random choice."""
    return random.choices(choices, weights=weights, k=1)[0]
