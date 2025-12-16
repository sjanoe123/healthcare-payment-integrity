#!/usr/bin/env python3
"""Seed ChromaDB with sample healthcare policy documents."""
from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from rag import ChromaStore


# Comprehensive policy documents for the prototype RAG system
SAMPLE_POLICIES = [
    # NCCI Policy Documents
    {
        "content": """NCCI Procedure-to-Procedure (PTP) Edits Overview:
The National Correct Coding Initiative (NCCI) was implemented to promote correct coding
methodologies and to control improper coding leading to inappropriate payment in Part B claims.

PTP edits define pairs of Healthcare Common Procedure Coding System (HCPCS)/Current
Procedural Terminology (CPT) codes that should not be reported together for a variety of reasons:
- The code pair represents procedures that cannot reasonably be performed at the same anatomic site
- The code pair represents procedures that cannot reasonably be performed at the same session
- One code is a component of a more comprehensive code

When a PTP edit is triggered, the column 2 code is typically denied unless an appropriate
modifier is applied to indicate the procedures were performed in different sessions or
anatomic sites.""",
        "metadata": {"source": "NCCI Policy Manual", "chapter": "1", "topic": "PTP Edits"},
    },
    {
        "content": """NCCI Medically Unlikely Edits (MUE) Overview:
MUE edits are used to reduce the paid units of service for a HCPCS/CPT code on the same
date of service by the same provider to a beneficiary.

MUE values are based on anatomic considerations, HCPCS/CPT code descriptors, CPT coding
instructions, nature of service/procedure, and clinical judgments about medical necessity.

Example MUE limits:
- Evaluation and Management (E/M) codes 99213-99215: MUE limit of 1 per day
- Physical therapy codes: Typically limited based on clinical guidelines
- Lab tests: May be limited based on medical necessity

If units of service exceed the MUE value, the excess units will be denied.""",
        "metadata": {"source": "NCCI Policy Manual", "chapter": "2", "topic": "MUE Edits"},
    },
    {
        "content": """NCCI Modifier Indicators:
The modifier indicator (0, 1, or 9) in NCCI PTP edits determines whether a modifier
can be used to bypass the edit:

- Modifier Indicator 0: There are no modifiers that allow the code pair to be billed together.
  These represent mutually exclusive codes that cannot be performed on the same patient
  on the same day by the same provider.

- Modifier Indicator 1: Appropriate modifiers (25, 59, XE, XS, XP, XU) may bypass the edit
  when the two procedures are performed in distinct/separate sessions, anatomic sites,
  or represent separately identifiable services.

- Modifier Indicator 9: The edit does not apply (typically represents deleted edits).

Common modifiers used to bypass PTP edits:
- Modifier 59: Distinct procedural service
- Modifier XE: Separate encounter
- Modifier XS: Separate structure
- Modifier XP: Separate practitioner
- Modifier XU: Unusual non-overlapping service""",
        "metadata": {"source": "NCCI Policy Manual", "chapter": "3", "topic": "Modifier Indicators"},
    },
    {
        "content": """NCCI MUE Adjudication Indicators:
The MUE Adjudication Indicator (MAI) determines how MUE edits are applied:

- MAI 1 (Claim Line): The MUE is applied to each claim line. Units exceeding the MUE
  are denied on a line-by-line basis.

- MAI 2 (Date of Service): The MUE is applied to all lines with the same code on the
  same date of service. Total units across all lines cannot exceed the MUE.

- MAI 3 (Date of Service with Modifier): Similar to MAI 2, but some modifiers may
  allow separate calculations for distinct anatomic sites or sessions.

Providers should:
1. Review MUE values before billing
2. Ensure documentation supports medical necessity for all units
3. Report accurate units of service
4. Appeal with supporting documentation if denial is inappropriate""",
        "metadata": {"source": "NCCI Policy Manual", "chapter": "4", "topic": "MUE Adjudication"},
    },

    # LCD/NCD Coverage Documents
    {
        "content": """Local Coverage Determination (LCD) Overview:
LCDs are coverage decisions made by Medicare Administrative Contractors (MACs) to
determine whether a particular item or service is reasonable and necessary.

Key elements of LCD coverage include:
- Covered ICD-10-CM diagnosis codes
- Non-covered diagnoses
- Covered CPT/HCPCS codes
- Documentation requirements
- Utilization guidelines

Before billing Medicare for a service, providers should verify that the service is
covered under the applicable LCD and that all documentation requirements are met.

Common reasons for LCD denial:
- Diagnosis code not on covered list
- Missing required documentation
- Frequency limits exceeded
- Service not medically necessary for the diagnosis""",
        "metadata": {"source": "CMS LCD Guidelines", "chapter": "General", "topic": "LCD Overview"},
    },
    {
        "content": """National Coverage Determination (NCD) vs LCD:
NCDs are national coverage policies issued by CMS that apply to all Medicare beneficiaries.
LCDs are local policies developed by MACs that apply only within their jurisdiction.

Key differences:
- NCDs take precedence over LCDs
- NCDs apply uniformly across the country
- LCDs may vary by MAC jurisdiction
- LCDs can be more restrictive but not more permissive than NCDs

When coverage conflicts exist:
1. Check NCD first for national coverage requirements
2. Check applicable LCD for additional local requirements
3. Ensure documentation meets both NCD and LCD criteria
4. Appeal with supporting medical evidence if denial is inappropriate""",
        "metadata": {"source": "CMS Coverage", "chapter": "NCD vs LCD", "topic": "Coverage Hierarchy"},
    },
    {
        "content": """LCD Medical Necessity Documentation Requirements:
To establish medical necessity for services covered under an LCD, documentation must include:

1. Clinical History:
   - Patient's presenting symptoms
   - Duration and progression of condition
   - Previous treatments and responses
   - Relevant co-morbidities

2. Physical Examination:
   - Objective findings supporting the diagnosis
   - Functional limitations
   - Clinical measurements (if applicable)

3. Diagnostic Test Results:
   - Laboratory values
   - Imaging findings
   - Other diagnostic procedure results

4. Treatment Plan:
   - Why the specific service is needed
   - Expected outcome
   - Alternative treatments considered

Documentation must be made at the time of service or prior to service for pre-authorization.""",
        "metadata": {"source": "CMS LCD Guidelines", "chapter": "Documentation", "topic": "Medical Necessity"},
    },

    # OIG and Compliance Documents
    {
        "content": """OIG Exclusion List (LEIE) Requirements:
The Office of Inspector General (OIG) maintains the List of Excluded Individuals/Entities (LEIE).
Healthcare providers and entities must check this list before employing or contracting with
any individual or entity.

Billing for services provided by excluded providers is prohibited and may result in:
- Denial of payment
- Civil monetary penalties
- Program exclusion
- Criminal prosecution

Providers should verify all employees and contractors against the LEIE monthly and
maintain documentation of these checks.""",
        "metadata": {"source": "OIG LEIE", "chapter": "Compliance", "topic": "Exclusion Screening"},
    },
    {
        "content": """OIG Exclusion Types and Mandatory Exclusion:
The OIG has both mandatory and permissive exclusion authority.

Mandatory Exclusion (Minimum 5 Years):
- Conviction of program-related crimes
- Conviction of patient abuse or neglect
- Felony conviction for healthcare fraud
- Felony conviction for controlled substance offenses

Permissive Exclusion (Length varies):
- Misdemeanor healthcare fraud
- License revocation or suspension
- Default on Health Education Assistance loans
- Failure to provide required information
- Obstruction of investigations

Reinstatement requires:
1. Serving the minimum exclusion period
2. Submitting reinstatement application
3. OIG approval (not automatic)""",
        "metadata": {"source": "OIG LEIE", "chapter": "Exclusion Types", "topic": "Mandatory vs Permissive"},
    },
    {
        "content": """OIG Work Plan - Common Audit Focus Areas:
The OIG Work Plan identifies areas of focus for investigations and audits. Current priorities include:

Medicare Part B:
- High-cost drugs and drug pricing
- Telehealth services billing
- Evaluation and Management coding accuracy
- Durable Medical Equipment (DME) fraud
- Laboratory testing medical necessity

Medicare Part A:
- Hospital readmissions
- Inpatient vs outpatient status
- Critical access hospital billing
- Skilled nursing facility services

Compliance Programs should:
- Review OIG Work Plan annually
- Conduct self-audits in focus areas
- Implement corrective action plans
- Train staff on identified risk areas""",
        "metadata": {"source": "OIG Work Plan", "chapter": "Audit Focus", "topic": "Priority Areas"},
    },

    # FWA Detection Documents
    {
        "content": """Fraud, Waste, and Abuse (FWA) Detection Indicators:
Common red flags that may indicate potential FWA include:

1. Billing Patterns:
   - Unusually high volume of services
   - Billing for services not rendered
   - Upcoding (billing for more expensive services)
   - Unbundling (billing separately for bundled services)

2. Provider Patterns:
   - Services provided outside specialty
   - Geographic outliers (patients traveling unusual distances)
   - High percentage of cash-pay patients

3. Documentation Issues:
   - Missing or inadequate documentation
   - Clone documentation (identical notes for different patients)
   - Services not supported by medical necessity

These indicators should trigger additional review and investigation.""",
        "metadata": {"source": "FWA Guidelines", "chapter": "Detection", "topic": "Red Flags"},
    },
    {
        "content": """Common Healthcare Fraud Schemes:
OIG and DOJ have identified common fraud schemes in healthcare:

1. Upcoding:
   - Billing higher-level E/M codes than supported
   - Using modifiers inappropriately to increase payment
   - Reporting more complex procedures than performed

2. Unbundling:
   - Billing component codes when a comprehensive code should be used
   - Separating bilateral procedures into two claims
   - Fragmenting services across multiple dates

3. Phantom Billing:
   - Billing for services never rendered
   - Billing for patients not seen
   - Duplicating claims for the same service

4. Kickback Schemes:
   - Payments for patient referrals
   - Free rent or services in exchange for referrals
   - Marketing arrangements that violate Anti-Kickback Statute

5. Identity Theft:
   - Using patient identities without authorization
   - Billing under deceased patient Medicare numbers
   - Ordering services for fictitious patients""",
        "metadata": {"source": "DOJ/OIG", "chapter": "Fraud Schemes", "topic": "Common Patterns"},
    },
    {
        "content": """Whistleblower (Qui Tam) Provisions and False Claims Act:
The False Claims Act allows private citizens to file lawsuits on behalf of the government
against entities that have defrauded federal programs.

Key provisions:
- Whistleblowers (relators) can receive 15-30% of recovered funds
- Protection against retaliation by employer
- Treble damages (3x actual damages) plus penalties

Common False Claims Act violations in healthcare:
- Billing for services not rendered
- Upcoding or unbundling
- Falsifying medical records
- Kickback arrangements
- Lack of medical necessity

Penalties:
- Civil penalties of $11,803 to $23,607 per false claim (2024)
- Treble damages
- Potential criminal prosecution
- Exclusion from federal healthcare programs""",
        "metadata": {"source": "DOJ", "chapter": "False Claims Act", "topic": "Qui Tam"},
    },

    # Billing and Coding Guidelines
    {
        "content": """Global Surgery Period and Modifier Requirements:
When a procedure has a global surgery period (010 or 090 days), all related E/M services
during this period are included in the surgical payment.

To separately report E/M services during the global period:
- Modifier 24: Unrelated E/M service by same physician during postoperative period
- Modifier 25: Significant, separately identifiable E/M service on same day as procedure
- Modifier 57: Decision for surgery made during the E/M encounter

Documentation must clearly support that the E/M service was:
1. Significant and separately identifiable, AND
2. Above and beyond the usual pre/postoperative work included in the global package

Failure to properly document and apply modifiers may result in claim denial or
potential audit findings.""",
        "metadata": {"source": "CMS MPFS", "chapter": "Global Surgery", "topic": "Modifiers"},
    },
    {
        "content": """Evaluation and Management (E/M) Coding Guidelines (2021+):
Since 2021, E/M office visit coding is based on Medical Decision Making (MDM) or Time.

Medical Decision Making Elements:
1. Number and Complexity of Problems Addressed
2. Amount and/or Complexity of Data Reviewed
3. Risk of Complications, Morbidity, or Mortality

MDM Levels for Office Visits:
- Straightforward (99202/99212): Minimal problems, minimal data, low risk
- Low (99203/99213): Low problems, limited data, low risk
- Moderate (99204/99214): Moderate problems, moderate data, moderate risk
- High (99205/99215): High problems, extensive data, high risk

Time-Based Billing:
- Document total time spent on the date of encounter
- Include all qualifying activities (pre-visit, face-to-face, post-visit)
- Use CPT-defined time thresholds for code selection""",
        "metadata": {"source": "CMS E/M Guidelines", "chapter": "Office Visits", "topic": "E/M Coding 2021+"},
    },
    {
        "content": """Modifier Usage and NCCI Compliance:
Proper modifier usage is critical for NCCI compliance and accurate reimbursement.

Key Modifiers and Their Use:
- Modifier 25: Significant, separately identifiable E/M service on same day as procedure
- Modifier 59/X{EPSU}: Distinct procedural service - different session, site, organ system
- Modifier 76: Repeat procedure by same physician
- Modifier 77: Repeat procedure by another physician
- Modifier 78: Unplanned return to OR during global period
- Modifier 79: Unrelated procedure during global period
- Modifier 91: Repeat clinical lab test (same day, same specimen)

Best Practices:
1. Only use modifiers when criteria are met
2. Document the distinctness of services
3. Avoid routine modifier application without justification
4. Review claims with modifiers for patterns suggesting misuse""",
        "metadata": {"source": "CMS Coding", "chapter": "Modifiers", "topic": "NCCI Compliance"},
    },
    {
        "content": """Telehealth Billing Requirements:
Medicare covers telehealth services when specific requirements are met:

Patient Location (Originating Site):
- Rural areas (health professional shortage areas)
- Certain exceptions during public health emergencies
- Patient's home (for certain services)

Provider Requirements:
- Eligible practitioners (physicians, NPs, PAs, etc.)
- Real-time audio-video technology
- HIPAA-compliant platform
- State licensure requirements

Billing Guidelines:
- Use modifier 95 for synchronous telehealth
- Place of Service (POS) code 02 for telehealth
- Document that visit was conducted via telehealth
- Maintain same documentation standards as in-person visits

FWA Risks in Telehealth:
- Services not actually provided
- Upcoding due to lack of physical exam
- Prescribing without appropriate evaluation
- Patient not present at qualifying location""",
        "metadata": {"source": "CMS Telehealth", "chapter": "Requirements", "topic": "Telehealth Billing"},
    },
    {
        "content": """Durable Medical Equipment (DME) Fraud Prevention:
DME is a high-risk category for fraud. Common issues include:

Red Flags:
- Equipment never delivered
- Beneficiary didn't need or request equipment
- No face-to-face encounter documented
- Inappropriate use of ABN (Advance Beneficiary Notice)
- Equipment billed that doesn't match prescription

Documentation Requirements:
- Face-to-face encounter within specified timeframe
- Written prescription with detailed item specifications
- Proof of delivery signed by beneficiary
- Medical necessity established in records
- Certificate of Medical Necessity when required

Prior Authorization:
- Required for many DME items
- Must be obtained before delivery
- Valid for specific timeframe
- Attached to claim for payment""",
        "metadata": {"source": "CMS DME", "chapter": "Fraud Prevention", "topic": "DME Compliance"},
    },

    # Clinical Guidelines
    {
        "content": """USPSTF Preventive Care Recommendations:
The U.S. Preventive Services Task Force (USPSTF) provides evidence-based recommendations.

Grade A Recommendations (High Certainty, Substantial Benefit):
- Colorectal cancer screening (ages 45-75)
- Cervical cancer screening (ages 21-65)
- Breast cancer screening (ages 50-74, biennial)
- Blood pressure screening (ages 18+)
- Hepatitis C screening (ages 18-79)

Grade B Recommendations (High Certainty, Moderate Benefit):
- Depression screening (adults)
- Prediabetes/Type 2 diabetes screening (ages 35-70, overweight/obese)
- Lung cancer screening (ages 50-80, 20+ pack-year history)
- STI screening (sexually active)

Coverage Implications:
- Medicare covers Grade A and B recommendations without cost-sharing
- Claims for screenings should align with USPSTF guidelines
- Overutilization of screenings may indicate FWA""",
        "metadata": {"source": "USPSTF", "chapter": "Preventive Care", "topic": "Screening Recommendations"},
    },
    {
        "content": """Choosing Wisely - Low-Value Care to Avoid:
The Choosing Wisely campaign identifies commonly overused tests and treatments.

Common Low-Value Services:
- Imaging for low back pain in first 6 weeks
- Preoperative testing for low-risk surgeries
- Annual EKG or cardiac screening in asymptomatic adults
- Routine vitamin D screening
- PSA screening without shared decision-making
- Antibiotics for upper respiratory infections
- Opioids as first-line treatment for chronic pain
- Continuous pulse oximetry monitoring for stable patients

Implications for Claims Review:
- High volume of low-value services may indicate overutilization
- Lack of supporting diagnosis for tests raises questions
- Pattern analysis can identify providers with outlier ordering patterns
- Documentation should support medical necessity for any ordered test""",
        "metadata": {"source": "Choosing Wisely", "chapter": "Low-Value Care", "topic": "Overutilization"},
    },

    # Specific Service Line Policies
    {
        "content": """Laboratory Testing Medical Necessity:
Laboratory tests must be medically necessary and appropriately ordered.

Standing Orders:
- May be used for recurring, predictable testing
- Must be based on individual patient assessment
- Should specify frequency and duration
- Require periodic review and renewal

Repeat/Reflex Testing:
- Must be clinically indicated
- Modifier 91 for repeat tests on same day
- Documentation of clinical rationale required

Common Medical Necessity Issues:
- Testing without supporting diagnosis
- Panels when individual tests would suffice
- Excessive frequency of monitoring
- Reflexive ordering without clinical indication

LCD Compliance:
- Verify diagnosis codes are on covered list
- Check frequency limitations
- Ensure ordering provider is eligible
- Document clinical need for each test""",
        "metadata": {"source": "CMS Lab", "chapter": "Medical Necessity", "topic": "Laboratory Compliance"},
    },
    {
        "content": """Physical Therapy and Rehabilitation Services:
Therapy services require ongoing documentation of medical necessity and progress.

Documentation Requirements:
- Initial evaluation with baseline measurements
- Treatment plan with specific goals
- Regular progress notes (at least every 10 visits)
- Functional outcome measurements
- Physician certification at start and every 90 days

Therapy Cap Exceptions:
- Services exceeding $2,330 annual limit require KX modifier
- Documentation must support skilled therapy need
- Targeted medical review may be triggered

Red Flags for FWA:
- Services without measurable progress
- Identical treatment plans across patients
- Exceeding typical treatment frequencies
- Services after patient reached plateau
- Group therapy billed as individual

Modifier Usage:
- GP: Physical therapy services
- GO: Occupational therapy services
- GN: Speech-language pathology services""",
        "metadata": {"source": "CMS Therapy", "chapter": "Rehabilitation", "topic": "Therapy Services"},
    },
    {
        "content": """Pain Management and Controlled Substances:
Pain management services require careful compliance monitoring.

Documentation Requirements:
- Initial comprehensive pain assessment
- Treatment plan with specific objectives
- Risk assessment for opioid therapy
- Prescription Drug Monitoring Program (PDMP) checks
- Periodic reassessment of treatment effectiveness
- Informed consent and treatment agreements

Red Flags:
- High-volume prescribing patterns
- Patients traveling long distances
- Cash payments for services
- Missing urine drug screens
- Early refill requests
- Multiple prescribers (doctor shopping)
- Injections without trial of conservative therapy

Intervention Guidelines:
- Facet joint injections limited per LCD
- Epidural steroid injections typically 3 per year
- Documentation of failed conservative treatment
- Imaging to support anatomic diagnosis""",
        "metadata": {"source": "CMS Pain Management", "chapter": "Controlled Substances", "topic": "Pain Management"},
    },
    {
        "content": """Cardiac Testing Medical Necessity:
Cardiac tests require clinical indication and proper documentation.

Stress Testing Indications:
- Evaluation of chest pain
- Known CAD with new symptoms
- Pre-operative risk assessment (specific criteria)
- Post-revascularization assessment

Echocardiography Indications:
- Murmur evaluation
- Heart failure assessment
- Valve disease evaluation
- Post-MI evaluation

Overutilization Concerns:
- Routine pre-operative testing without indication
- Repeat testing without clinical change
- Screening in asymptomatic low-risk patients
- Multiple same-day cardiac tests without clear rationale

LCD Coverage:
- Specific diagnosis codes required
- Frequency limitations may apply
- Prior testing results should be reviewed
- Documentation of symptoms/clinical findings essential""",
        "metadata": {"source": "CMS Cardiology", "chapter": "Cardiac Testing", "topic": "Medical Necessity"},
    },
]


def seed_chromadb():
    """Seed the ChromaDB with sample policy documents."""
    print("Initializing ChromaDB...")
    store = ChromaStore(persist_dir="./data/chroma", collection_name="policies")

    print(f"Current document count: {store.count()}")

    if store.count() > 0:
        print("Clearing existing documents...")
        store.clear()

    print(f"Adding {len(SAMPLE_POLICIES)} policy documents...")

    documents = [p["content"] for p in SAMPLE_POLICIES]
    metadatas = [p["metadata"] for p in SAMPLE_POLICIES]
    ids = [f"policy_{i}" for i in range(len(SAMPLE_POLICIES))]

    store.add_documents(documents=documents, metadatas=metadatas, ids=ids)

    print(f"Done! Total documents: {store.count()}")

    # Test search
    print("\nTesting search...")
    results = store.search("NCCI PTP edits billing", n_results=2)
    for r in results:
        print(f"  - {r['metadata'].get('topic', 'Unknown')}: {r['content'][:100]}...")


if __name__ == "__main__":
    seed_chromadb()
