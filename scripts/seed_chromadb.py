#!/usr/bin/env python3
"""Seed ChromaDB with sample healthcare policy documents."""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from rag import ChromaStore

# Policy content effective dates
POLICY_EFFECTIVE_DATE = "2024-01-01"  # When CMS policies became effective
LAST_REVIEWED_DATE = "2024-12-17"  # When content was last verified


def validate_policies(policies: list[dict]) -> tuple[bool, list[str]]:
    """Validate policy document structure and content.

    Args:
        policies: List of policy dictionaries to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    topics = []

    for i, policy in enumerate(policies):
        # Check required fields
        if "content" not in policy:
            errors.append(f"Policy {i}: missing content")
        elif len(policy["content"]) < 100:
            errors.append(
                f"Policy {i}: content too short ({len(policy['content'])} chars)"
            )

        if "metadata" not in policy:
            errors.append(f"Policy {i}: missing metadata")
        else:
            metadata = policy["metadata"]
            required_keys = ["source", "chapter", "topic"]
            for key in required_keys:
                if key not in metadata:
                    errors.append(f"Policy {i}: missing metadata.{key}")

            # Track topics for duplicate check
            if "topic" in metadata:
                topics.append(metadata["topic"])

    # Check for duplicate topics
    seen = set()
    duplicates = []
    for topic in topics:
        if topic in seen:
            duplicates.append(topic)
        seen.add(topic)

    if duplicates:
        errors.append(f"Duplicate topics found: {duplicates}")

    return len(errors) == 0, errors


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
        "metadata": {
            "source": "NCCI Policy Manual",
            "chapter": "1",
            "topic": "PTP Edits",
        },
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
        "metadata": {
            "source": "NCCI Policy Manual",
            "chapter": "2",
            "topic": "MUE Edits",
        },
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
        "metadata": {
            "source": "NCCI Policy Manual",
            "chapter": "3",
            "topic": "Modifier Indicators",
        },
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
        "metadata": {
            "source": "NCCI Policy Manual",
            "chapter": "4",
            "topic": "MUE Adjudication",
        },
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
        "metadata": {
            "source": "CMS LCD Guidelines",
            "chapter": "General",
            "topic": "LCD Overview",
        },
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
        "metadata": {
            "source": "CMS Coverage",
            "chapter": "NCD vs LCD",
            "topic": "Coverage Hierarchy",
        },
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
        "metadata": {
            "source": "CMS LCD Guidelines",
            "chapter": "Documentation",
            "topic": "LCD Documentation Requirements",
        },
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
        "metadata": {
            "source": "OIG LEIE",
            "chapter": "Compliance",
            "topic": "Exclusion Screening",
        },
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
        "metadata": {
            "source": "OIG LEIE",
            "chapter": "Exclusion Types",
            "topic": "Mandatory vs Permissive",
        },
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
        "metadata": {
            "source": "OIG Work Plan",
            "chapter": "Audit Focus",
            "topic": "Priority Areas",
        },
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
        "metadata": {
            "source": "FWA Guidelines",
            "chapter": "Detection",
            "topic": "Red Flags",
        },
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
        "metadata": {
            "source": "DOJ/OIG",
            "chapter": "Fraud Schemes",
            "topic": "Common Patterns",
        },
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
        "metadata": {
            "source": "DOJ",
            "chapter": "False Claims Act",
            "topic": "Qui Tam",
        },
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
        "metadata": {
            "source": "CMS MPFS",
            "chapter": "Global Surgery",
            "topic": "Modifiers",
        },
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
        "metadata": {
            "source": "CMS E/M Guidelines",
            "chapter": "Office Visits",
            "topic": "E/M Coding 2021+",
        },
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
        "metadata": {
            "source": "CMS Coding",
            "chapter": "Modifiers",
            "topic": "NCCI Compliance",
        },
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
        "metadata": {
            "source": "CMS Telehealth",
            "chapter": "Requirements",
            "topic": "Telehealth Billing",
        },
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
        "metadata": {
            "source": "CMS DME",
            "chapter": "Fraud Prevention",
            "topic": "DME Compliance",
        },
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
        "metadata": {
            "source": "USPSTF",
            "chapter": "Preventive Care",
            "topic": "Screening Recommendations",
        },
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
        "metadata": {
            "source": "Choosing Wisely",
            "chapter": "Low-Value Care",
            "topic": "Overutilization",
        },
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
        "metadata": {
            "source": "CMS Lab",
            "chapter": "Medical Necessity",
            "topic": "Laboratory Compliance",
        },
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
        "metadata": {
            "source": "CMS Therapy",
            "chapter": "Rehabilitation",
            "topic": "Therapy Services",
        },
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
        "metadata": {
            "source": "CMS Pain Management",
            "chapter": "Controlled Substances",
            "topic": "Pain Management",
        },
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
        "metadata": {
            "source": "CMS Cardiology",
            "chapter": "Cardiac Testing",
            "topic": "Cardiac Testing Guidelines",
        },
    },
    # ============================================================
    # CATEGORY 1: SPECIALTY-SPECIFIC POLICIES (12 documents)
    # ============================================================
    {
        "content": """Radiology and Diagnostic Imaging Guidelines:
Diagnostic imaging services must be medically necessary and appropriately ordered.

Technical Component (TC) vs Professional Component (PC):
- TC (modifier TC): Equipment, supplies, technologist time
- PC (modifier 26): Physician interpretation and report
- Global (no modifier): Both TC and PC together

CT/MRI Medical Necessity:
- Clinical indication must support the study
- Prior conservative treatment should be documented
- Repeat imaging requires clinical change or new symptoms
- Comparison with prior studies when available

Common Denial Reasons:
- Routine screening without symptoms
- Duplicate imaging in short timeframe
- Inappropriate body region for diagnosis
- Missing clinical documentation

Authorization Requirements:
- Many advanced imaging services require prior authorization
- Must specify body part, clinical indication, and laterality
- CT/MRI of spine, brain, joints commonly require PA
- Emergency services may have retrospective review""",
        "metadata": {
            "source": "CMS Radiology",
            "chapter": "Imaging Guidelines",
            "topic": "Diagnostic Imaging",
        },
    },
    {
        "content": """Surgical Services Billing and Documentation:
Surgical procedures require comprehensive documentation and accurate coding.

Operative Report Requirements:
- Pre-operative diagnosis
- Post-operative diagnosis
- Procedure(s) performed
- Surgeon(s) and assistants
- Anesthesia type
- Findings and technique description
- Specimens removed
- Estimated blood loss
- Complications (if any)

Multiple Procedure Billing:
- Primary procedure: 100% of fee schedule
- Secondary procedures: 50% reduction typically applies
- Bilateral procedures: Use modifier 50 or RT/LT
- Distinct procedures: May require modifier 59/XE/XS/XP/XU

Assistant Surgeon Rules:
- Modifier AS: Physician assistant at surgery
- Modifier 80: Assistant surgeon
- Modifier 82: Assistant surgeon when qualified resident unavailable
- Not all procedures allow assistant surgeon billing

Same-Day E/M with Surgery:
- Modifier 57: Decision for major surgery
- Modifier 25: Significant, separately identifiable E/M
- Must document distinct service beyond pre-op evaluation""",
        "metadata": {
            "source": "CMS Surgery",
            "chapter": "Surgical Services",
            "topic": "Operative Billing",
        },
    },
    {
        "content": """Mental and Behavioral Health Services:
Psychiatric services have specific documentation and coding requirements.

Psychiatric Evaluation Codes:
- 90791: Psychiatric diagnostic evaluation (no medical services)
- 90792: Psychiatric diagnostic evaluation with medical services
- Time documented not required but recommended

Psychotherapy Codes (Time-Based):
- 90832: 16-37 minutes
- 90834: 38-52 minutes
- 90837: 53+ minutes
- Add-on codes for psychotherapy with E/M same day

Documentation Requirements:
- Chief complaint and symptoms
- Mental status examination
- Diagnostic assessment
- Treatment plan
- Progress toward goals

Crisis Services:
- 90839: First 30-74 minutes of crisis psychotherapy
- 90840: Each additional 30 minutes
- Must document urgent/crisis nature
- Distinct from routine psychotherapy

Telehealth Mental Health:
- Many services eligible for telehealth delivery
- Modifier 95 for synchronous telehealth
- Audio-only services have specific codes (99441-99443)
- State licensure requirements apply""",
        "metadata": {
            "source": "CMS Behavioral Health",
            "chapter": "Mental Health",
            "topic": "Psychiatric Services",
        },
    },
    {
        "content": """Emergency Department Services:
ED E/M coding follows specific medical decision making criteria.

ED E/M Levels (99281-99285):
- 99281: Self-limited/minor problem
- 99282: Low severity
- 99283: Moderate severity
- 99284: High severity without threat
- 99285: High severity with threat to life/function

Documentation for Medical Decision Making:
1. Number and complexity of problems
2. Amount and complexity of data reviewed
3. Risk of complications and management options

Critical Care (99291-99292):
- Requires life-threatening condition
- Time-based: 30-74 minutes = 99291
- Each additional 30 minutes = 99292
- Document total time and activities
- Cannot bill concurrent with some other services

Observation Status:
- G0378: Observation per hour (hospital use)
- 99218-99220: Initial observation care (physician)
- 99224-99226: Subsequent observation care
- Must document medical necessity for observation

Separate from ED E/M:
- Procedures with separate CPT codes
- Critical care (document distinct time)
- Prolonged services (if applicable)""",
        "metadata": {
            "source": "CMS Emergency",
            "chapter": "Emergency Services",
            "topic": "ED Coding",
        },
    },
    {
        "content": """Anesthesia Services Billing:
Anesthesia billing uses time-based units plus base units.

Anesthesia Payment Formula:
Payment = (Base Units + Time Units + Modifying Units) × Conversion Factor

Time Calculations:
- Anesthesia time begins when anesthesiologist begins preparation
- Ends when patient safely transferred to post-anesthesia care
- One time unit = 15 minutes typically
- Document start and stop times precisely

Physical Status Modifiers:
- P1: Normal healthy patient
- P2: Patient with mild systemic disease
- P3: Patient with severe systemic disease
- P4: Patient with severe disease, constant threat to life
- P5: Moribund patient not expected to survive
- P6: Declared brain-dead organ donor

Medical Direction (Modifiers AA, AD, QK, QX, QY, QZ):
- AA: Anesthesiologist personally performs
- AD: Medical supervision, more than 4 concurrent cases
- QK: Medical direction of 2-4 concurrent cases (CRNA)
- QX: CRNA service with medical direction
- QY: Medical direction of one CRNA
- QZ: CRNA service without medical direction

Documentation Requirements:
- Pre-anesthesia evaluation
- Anesthesia plan
- Intraoperative record (vital signs, drugs, fluids)
- Post-anesthesia evaluation
- Discharge criteria met""",
        "metadata": {
            "source": "CMS Anesthesia",
            "chapter": "Anesthesia",
            "topic": "Anesthesia Billing",
        },
    },
    {
        "content": """Pathology and Laboratory Services:
Lab testing requires medical necessity and proper ordering.

Clinical Laboratory Tests:
- Must be ordered by treating physician/qualified practitioner
- Standing orders require specific patient assessment
- Results must be documented and used for patient care

Automated Test Panels:
- 80047-80081: Organ/disease-oriented panels
- Each component must be medically necessary
- Cannot unbundle panel codes for additional payment
- Order individual tests when full panel not needed

Molecular Diagnostics:
- 81105-81479: Molecular pathology codes
- 0001U-0XXX: Proprietary laboratory analyses (PLAs)
- Often require prior authorization
- Medical necessity documentation critical

Pathology Services:
- 88300-88309: Surgical pathology levels
- 88321: Consultation and report on referred material
- 88323: Consultation during surgery
- 88360-88377: Special stains and immunohistochemistry

Compliance Issues:
- Billing for tests not performed
- Unbundling comprehensive panels
- Duplicate testing without clinical indication
- Reflexive testing without medical necessity
- Standing orders without appropriate oversight""",
        "metadata": {
            "source": "CMS Laboratory",
            "chapter": "Pathology/Lab",
            "topic": "Laboratory Services",
        },
    },
    {
        "content": """Home Health Services Requirements:
Home health requires certification and face-to-face documentation.

Eligibility Requirements:
- Homebound status (confined to home)
- Need for skilled services
- Under care of a physician
- Face-to-face encounter within required timeframe

Face-to-Face Encounter:
- Required within 90 days prior or 30 days after start of care
- Must document clinical findings supporting homebound status
- Must document need for skilled services
- Can be performed by physician or allowed NPP

Skilled Services Covered:
- Skilled nursing (assessment, teaching, wound care)
- Physical therapy
- Occupational therapy
- Speech-language pathology
- Medical social services (under supervision)
- Home health aide (only with other skilled service)

Plan of Care Requirements:
- Certification by physician
- Recertification every 60 days
- Specify services, frequency, duration
- Must be consistent with face-to-face findings

OASIS Assessment:
- Required at start of care, resumption, recertification
- Comprehensive patient assessment
- Affects payment through case-mix adjustment
- Quality reporting based on OASIS data""",
        "metadata": {
            "source": "CMS Home Health",
            "chapter": "Home Health",
            "topic": "Home Health Services",
        },
    },
    {
        "content": """Skilled Nursing Facility (SNF) Services:
SNF billing follows prospective payment with consolidated billing.

Patient Driven Payment Model (PDPM):
- Replaced RUG-IV in October 2019
- Five case-mix components: PT, OT, SLP, Nursing, Non-Therapy Ancillary
- Based on patient characteristics, not therapy minutes
- Uses ICD-10-CM mapping for classification

SNF Consolidated Billing:
- SNF responsible for all Part A and most Part B services
- Physical therapy, occupational therapy, speech therapy
- Drugs and biologicals (with exceptions)
- Lab tests and X-rays
- DME and supplies (with exceptions)

Excluded from SNF Consolidated Billing:
- Physician services
- Certain high-cost drugs (excluded from SNF PPS)
- Ambulance transportation
- Chemotherapy
- Certain complex lab tests

3-Day Prior Hospital Stay:
- Traditional Medicare requires 3-day inpatient hospital stay
- Stay must be within 30 days of SNF admission
- Observation days do not count
- Medicare Advantage may waive requirement

Coverage Period:
- Up to 100 days per benefit period
- Days 1-20: No coinsurance
- Days 21-100: Daily coinsurance applies
- Must demonstrate continued need for skilled care""",
        "metadata": {
            "source": "CMS SNF",
            "chapter": "Skilled Nursing",
            "topic": "SNF Services",
        },
    },
    {
        "content": """Ambulance Services Medical Necessity:
Ambulance transport requires specific medical necessity criteria.

Medical Necessity Requirements:
- Transport by other means would endanger patient's health
- Patient's condition requires medical supervision during transport
- Must be to nearest appropriate facility
- Origin and destination requirements met

Levels of Service:
- A0425: Ground mileage
- A0426: ALS1 non-emergency
- A0427: ALS1 emergency
- A0428: BLS non-emergency
- A0429: BLS emergency
- A0430: ALS2 (advanced procedures)
- A0431: ALS2 supplies
- A0433: Advanced life support, level 2
- A0434: Specialty care transport

Documentation Requirements:
- Patient's condition at time of transport
- Medical necessity for ambulance (vs other transport)
- Services provided during transport
- Crew certifications (EMT, paramedic)
- Mileage (loaded miles)
- Origin and destination addresses

Non-Emergency Transport:
- Prior authorization often required
- Physician Certification Statement (PCS) needed
- Must justify why other transport inadequate
- Repetitive ambulance transport rules apply

Common Denial Reasons:
- Patient ambulatory/could use wheelchair van
- Missing PCS for non-emergency
- Transport not to nearest appropriate facility
- Documentation doesn't support level of service""",
        "metadata": {
            "source": "CMS Ambulance",
            "chapter": "Ambulance",
            "topic": "Ambulance Services",
        },
    },
    {
        "content": """Hospice Services and Election:
Hospice provides comfort care for terminally ill patients.

Eligibility:
- Certified terminal prognosis (6 months or less if disease runs normal course)
- Patient elects hospice benefit
- Waives Medicare Part A coverage for curative treatment of terminal illness

Election Process:
- Written election statement required
- Designates hospice provider
- Acknowledges palliative (not curative) focus
- Effective date specified
- Can revoke at any time

Certification Requirements:
- Initial certification: Hospice physician and attending physician
- Recertification periods: Two 90-day, then 60-day periods
- Face-to-face required before 3rd benefit period and subsequent
- Document clinical findings supporting prognosis

Levels of Care:
- Routine Home Care (RHC): Most common, daily rate
- Continuous Home Care (CHC): Crisis management, 8+ hours/day
- General Inpatient Care (GIP): Pain/symptom management
- Inpatient Respite Care: Caregiver relief, 5-day limit

Covered Services:
- Nursing care
- Physician services
- Medical social services
- Counseling (including bereavement)
- Physical therapy, occupational therapy, speech therapy
- Home health aide and homemaker
- Drugs for symptom control
- DME and supplies related to terminal diagnosis

Live Discharge:
- Patient revokes or condition improves
- Must document reason for discharge
- Can re-elect hospice if condition declines""",
        "metadata": {
            "source": "CMS Hospice",
            "chapter": "Hospice",
            "topic": "Hospice Services",
        },
    },
    {
        "content": """Oncology Services Billing:
Cancer treatment involves complex billing with drug administration and supportive care.

Chemotherapy Administration:
- 96401-96417: Chemotherapy administration codes
- 96409: IV push, single or initial substance
- 96413: IV infusion, up to 1 hour
- 96415: Each additional hour
- Hierarchy rules apply for concurrent infusions

Drug Billing (J-Codes):
- J9XXX: Antineoplastic drugs
- Billed per unit specified in HCPCS
- Average Sales Price (ASP) + 6% reimbursement
- Must document drug name, dose, route, diagnosis
- Wastage may be billed separately

Therapeutic Drug Monitoring:
- Drug levels for dosing adjustments
- Must be medically necessary
- Document clinical reason for monitoring

Supportive Care:
- Anti-emetics during chemotherapy
- Growth factors (G-CSF, EPO) - LCD restrictions
- Pain management
- Hydration therapy (96360-96361)

Oncology Care Model/Alternatives:
- Enhanced oncology medical home models
- Quality metrics and cost benchmarks
- Care management requirements
- Monthly enhanced oncology services (MEOS) payments

Prior Authorization:
- Many chemotherapy drugs require PA
- Document failed prior therapies if applicable
- Confirm diagnosis and staging
- Review LCD/NCD coverage criteria""",
        "metadata": {
            "source": "CMS Oncology",
            "chapter": "Oncology",
            "topic": "Cancer Treatment",
        },
    },
    {
        "content": """Wound Care Management and Debridement:
Wound care requires documentation of wound characteristics and treatment necessity.

Wound Assessment Documentation:
- Location and measurements (length × width × depth)
- Stage/classification of wound
- Wound bed description (granulation, slough, eschar)
- Periwound condition
- Drainage amount and type
- Pain level
- Progress from previous visit

Debridement Codes:
- 11042-11047: Active wound care management
  - 11042: Subcutaneous tissue, first 20 sq cm
  - 11043: Muscle and/or fascia, first 20 sq cm
  - 11044: Bone, first 20 sq cm
  - +11045-11047: Each additional 20 sq cm
- 97597-97602: Non-selective debridement

Negative Pressure Wound Therapy (NPWT):
- E2402: Stationary NPWT (DME)
- 97605-97608: NPWT application/management
- Coverage criteria include wound characteristics
- Prior authorization typically required
- Document wound measurements at each visit

Hyperbaric Oxygen Therapy (HBOT):
- 99183: Hyperbaric oxygen therapy supervision
- Limited covered diagnoses (diabetic wounds, radiation injury, etc.)
- 20-40 treatments typical course
- Must document objective wound improvement
- Prior authorization required

Medical Necessity:
- Wound must be non-healing with standard care
- Document failed conservative treatment
- Comorbidities affecting healing
- Nutritional status
- Infection control measures""",
        "metadata": {
            "source": "CMS Wound Care",
            "chapter": "Wound Care",
            "topic": "Wound Management",
        },
    },
    # ============================================================
    # CATEGORY 2: ADVANCED NCCI/BILLING (10 documents)
    # ============================================================
    {
        "content": """Global Surgery Package Deep Dive:
Understanding global periods is essential for accurate surgical billing.

Global Period Types:
- 000: Minor procedure, E/M on same day included
- 010: Minor procedure, 10-day postoperative period
- 090: Major procedure, 90-day postoperative period
- XXX: Global concept does not apply
- YYY: Carrier determines global period
- ZZZ: Add-on code, global of primary procedure

What's Included in the Global Package:
Pre-operative (day before and day of surgery):
- History and physical
- Obtaining informed consent
- Routine pre-operative care

Intra-operative:
- All procedures normally required for the surgery
- Local anesthesia
- Immediate post-operative care

Post-operative (010 or 090 days):
- Routine follow-up visits
- Complications not requiring return to OR
- Supplies (except those identified separately)
- Dressing changes
- Removal of sutures, tubes, drains

What's NOT Included:
- Unrelated E/M services (modifier 24)
- Return to OR for complication (modifier 78)
- Unrelated procedure during global (modifier 79)
- Significant, separately identifiable E/M same day (modifier 25)
- Decision for surgery (modifier 57)
- Staged procedure (modifier 58)""",
        "metadata": {
            "source": "CMS Global Surgery",
            "chapter": "Surgery",
            "topic": "Global Periods",
        },
    },
    {
        "content": """Modifier 25 Compliance Requirements:
Modifier 25 allows separate payment for significant, separately identifiable E/M services.

When to Use Modifier 25:
- E/M service same day as minor procedure (000 or 010 global)
- Service is significant and separately identifiable
- E/M is above and beyond usual pre/post-operative work
- Clearly distinct from work associated with procedure

Documentation Requirements:
- Separate chief complaint or problem addressed
- Separate history specific to E/M service
- Separate examination findings
- Separate medical decision making
- Documentation must stand alone to justify E/M level

Common Audit Findings:
- Using modifier 25 routinely without documentation
- E/M documentation indistinguishable from procedure note
- Same diagnosis supporting both procedure and E/M
- No distinct clinical decision making documented

Best Practices:
1. Document E/M elements separately from procedure note
2. Clearly identify the distinct problem or reason for E/M
3. Support the E/M level selected with documentation
4. Don't use modifier 25 for pre-procedure evaluation alone
5. Review claims with high modifier 25 usage rates

Red Flags for Auditors:
- Modifier 25 on every procedure claim
- High-level E/M codes with modifier 25
- Same ICD-10 code for procedure and E/M
- Templated documentation lacking specificity""",
        "metadata": {
            "source": "CMS Modifiers",
            "chapter": "Modifier 25",
            "topic": "E/M with Procedures",
        },
    },
    {
        "content": """Modifier 59 and X{EPSU} Modifiers Detailed Guidelines:
These modifiers indicate distinct procedural services that would otherwise be bundled.

Modifier 59 - Distinct Procedural Service:
- Different session/patient encounter
- Different site/organ system
- Separate incision/excision
- Separate injury (or area of injury)
- Bypass NCCI PTP edit when criteria met

X Modifier Subset (More Specific than 59):
- XE: Separate Encounter (distinct encounter/date)
- XS: Separate Structure (different organ/structure)
- XP: Separate Practitioner (different provider)
- XU: Unusual Non-Overlapping Service

When to Use Which:
- Use X modifiers when they precisely describe the situation
- Use modifier 59 only if no X modifier specifically applies
- X modifiers provide clearer audit trail
- Carriers may require X modifiers in future

Documentation Requirements:
- Clearly state what makes services distinct
- Different anatomic site: document specific locations
- Different session: document time separation
- Different organ system: document distinct diagnoses/indications

Common Misuse:
- Using 59/X modifiers to bypass legitimate bundles
- Applying without supporting documentation
- Using to unbundle inherently related services
- Routine application without clinical justification

Audit Triggers:
- High frequency of modifier 59/XE/XS/XP/XU usage
- Same modifier on all code pairs
- Missing documentation of distinctness
- Pattern of unbundling commonly bundled services""",
        "metadata": {
            "source": "CMS Modifiers",
            "chapter": "Modifier 59",
            "topic": "Distinct Services",
        },
    },
    {
        "content": """Split/Shared E/M Visit Rules:
Medicare rules for E/M services provided partly by physician and NPP.

Definition:
A split/shared visit is an E/M service where both a physician and
NPP (NP, PA, CNS) each personally perform a substantive portion
of the encounter.

2024+ Rules (Post-CY 2023):
- Substantive portion = more than half of total time OR
- Substantive portion = one of three key MDM elements
- Bill under the provider who performed substantive portion
- Both providers must document their contributions

Substantive Portion Options:
1. History
2. Physical examination
3. Medical decision making
4. OR more than half of total time

Documentation Requirements:
- Each provider documents their portion
- Clear identification of who did what
- Time (if using time basis) must be clearly documented
- Same-day notation of services

Billing Guidelines:
- Use -FS modifier when billing split/shared visits
- Facility setting only (not office/clinic)
- Both physician and NPP must be employed/contracted by same entity
- Cannot split/share with teaching physician rules

Compliance Considerations:
- Don't use to maximize reimbursement artificially
- Document authentic clinical involvement
- Avoid patterns suggesting abuse
- Ensure NPP works within scope of practice""",
        "metadata": {
            "source": "CMS E/M",
            "chapter": "Split/Shared",
            "topic": "Split Shared Visits",
        },
    },
    {
        "content": """Incident-To Billing Requirements:
Services furnished incident-to physician services may be billed under the physician.

Requirements for Incident-To:
1. Service must be integral part of physician's professional service
2. Commonly rendered in physician's office
3. Service must be commonly included in physician's bill
4. Physician must initiate course of treatment
5. Direct supervision required (physician in office suite)
6. Service furnished by auxiliary personnel

Direct Supervision Defined:
- Physician immediately available
- Present in same office suite
- Does not need to be in same room
- Telephonic availability NOT sufficient

Who Can Provide Incident-To Services:
- NPs, PAs, CNMs (if not billing independently)
- Registered nurses
- Medical assistants
- Other auxiliary personnel

Documentation Requirements:
- Physician documents initial service/treatment plan
- Progress notes indicate physician oversight
- Changes to treatment plan require physician involvement
- Medical record supports auxiliary personnel's competence

Location Restrictions:
- Office/clinic setting (not hospital)
- Provider-based clinics may have different rules
- Skilled nursing facility services have separate rules

Common Compliance Issues:
- Billing incident-to without direct supervision
- NPP provides care for new problem without physician
- Documentation doesn't show physician involvement
- Services in hospital setting billed as incident-to""",
        "metadata": {
            "source": "CMS Incident-To",
            "chapter": "Incident-To",
            "topic": "Auxiliary Services",
        },
    },
    {
        "content": """Critical Care Coding (99291-99292):
Critical care services require specific documentation and coding requirements.

Definition of Critical Care:
Care of critically ill/injured patients requiring high-complexity decision making
to prevent imminent death or failure of vital organ systems.

Time Requirements:
- 99291: 30-74 minutes (only bill once per date)
- 99292: Each additional 30 minutes
- Less than 30 minutes: Bill appropriate E/M code
- Time need not be continuous

What Counts as Critical Care Time:
- Time devoted exclusively to individual patient
- Bedside care
- Time on unit/floor working on patient's behalf
- Review of lab/imaging results
- Discussion with other providers
- Documentation (if performed during evaluation/management)
- Family discussions (if patient unable and medical necessity exists)

What Does NOT Count:
- Time separately reported procedures take
- Activities not requiring physician's attention
- Time patient doesn't require critical care
- Teaching activities

Services Included in Critical Care:
- Interpretation of cardiac output, chest X-rays, ABGs
- Gastric intubation
- Ventilator management
- Temporary transcutaneous pacing

Services Billed Separately:
- CPR
- Endotracheal intubation
- Central line placement
- Chest tube insertion

Documentation Must Include:
- Total critical care time
- Nature of critical illness
- Treatment rendered
- Complexity of decision making""",
        "metadata": {
            "source": "CMS Critical Care",
            "chapter": "Critical Care",
            "topic": "99291-99292",
        },
    },
    {
        "content": """Prolonged Services Coding Guidelines:
Prolonged services compensate for time beyond typical E/M service time.

Prolonged Services with Direct Patient Contact (Office):
- 99417: Each additional 15 minutes beyond time of highest level E/M
- Used only with 99205 or 99215
- Must exceed time threshold by at least 15 minutes
- Cannot bill 99417 alone

Time Thresholds for 99417:
- 99205: Total time 60-74 minutes (no 99417)
- 99205: Total time 75-89 minutes (1 unit 99417)
- 99205: Total time 90+ minutes (additional units)
- 99215: Total time 55-69 minutes (no 99417)
- 99215: Total time 70-84 minutes (1 unit 99417)

Prolonged Services Without Direct Contact (99358-99359):
- 99358: First hour (30 minutes minimum)
- 99359: Each additional 30 minutes
- Before or after direct patient care
- Does not require face-to-face contact
- Must be related to E/M service

Inpatient Prolonged Services:
- Hospital prolonged services rules differ
- Unit/floor time vs direct contact
- Different time thresholds apply

Documentation Requirements:
- Start and stop times
- Activities performed during prolonged time
- Medical necessity for extended time
- Cannot count separately billable procedure time

Common Errors:
- Billing without meeting minimum threshold
- Counting non-qualifying time
- Missing time documentation
- Using wrong codes for setting""",
        "metadata": {
            "source": "CMS Prolonged Services",
            "chapter": "Prolonged",
            "topic": "Extended E/M Time",
        },
    },
    {
        "content": """Add-On Code Requirements:
Add-on codes can only be reported with specified primary codes.

Add-On Code Characteristics:
- Identified by + symbol in CPT
- Never reported alone
- Exempt from multiple procedure reduction
- Must accompany primary procedure code
- Some have restricted primary code list

Common Add-On Code Examples:
- +11008: Removal of prosthetic material (with 11004-11006)
- +22614: Each additional level, posterior arthrodesis (with 22612)
- +33257: Additional surgical ablation (with 33256)
- +43273: Injection for sinogram (with 43260-43270)
- +99417: Prolonged services (with 99205, 99215)
- +96361: Hydration, each additional hour (with 96360)

Primary Code Requirements:
- Add-on requires specific primary code(s)
- Primary must be reported same session/date
- Cannot substitute similar codes
- Check CPT guidelines for allowed primaries

Modifier Usage with Add-Ons:
- Modifiers may apply to add-ons (laterality, etc.)
- Multiple procedure rules typically don't apply
- Units may be limited by primary procedure

Billing Rules:
- Report units based on service (time, segments, etc.)
- Some add-ons limited to one unit per primary
- Others allow multiple units
- Check MUE values for unit limits

Documentation Requirements:
- Support primary procedure documentation
- Additional documentation for add-on specifics
- Time documentation if time-based
- Anatomic specifics if location-based""",
        "metadata": {
            "source": "CMS Add-On Codes",
            "chapter": "Add-On",
            "topic": "Primary Code Requirements",
        },
    },
    {
        "content": """Separate Procedure Designation:
Some procedures are designated 'separate procedure' and have bundling rules.

Separate Procedure Definition:
Procedures commonly carried out as an integral component of a total service
or procedure are designated with '(separate procedure)' in CPT.

When to Report Separately:
- Performed independently of any other service
- Performed in different anatomic site
- Performed through different access
- Distinct from any other procedure

When NOT to Report Separately:
- When integral to another procedure
- When performed through same incision/access
- When part of more comprehensive service
- When NCCI bundles apply

Examples:
- Arthroscopic procedures: Diagnostic arthroscopy bundled with surgical
- Laparoscopic: Diagnostic laparoscopy bundled with surgical
- Excisions: May include adjacent tissue transfer
- Injections: May be bundled with procedure using same access

Documentation for Separate Reporting:
- Distinct medical necessity
- Different anatomic location clearly stated
- Different access/incision documented
- Clinical rationale for separate procedure

Modifier Usage:
- Modifier 59 or X modifiers may allow separate reporting
- Must meet distinctness criteria
- Documentation must support unbundling
- Cannot routinely unbundle integral services

Audit Considerations:
- High scrutiny for 'separate procedure' codes
- Patterns of unbundling trigger review
- Documentation must clearly support
- Medical necessity required for both services""",
        "metadata": {
            "source": "CMS Separate Procedure",
            "chapter": "Bundling",
            "topic": "Separate Procedure",
        },
    },
    {
        "content": """Multiple Procedure Payment Reduction (MPPR):
Payment reductions apply when multiple procedures performed same session.

Surgical Multiple Procedure Rules:
- Primary procedure: 100% of fee schedule
- Second through fifth procedures: 50% of fee schedule
- Additional procedures: by report
- Applies to procedures with indicator "2" or "3"

MPPR for Diagnostic Imaging:
- TC (technical component): 50% reduction for subsequent
- PC (professional component): May have separate MPPR
- Applies within family of related imaging codes
- Check CMS MPPR tables for specific reductions

MPPR for Therapy Services:
- 50% reduction applies to practice expense (PE)
- Applies when PT, OT, or SLP provided same day
- Always timed services: second service at 50% PE
- Work and malpractice RVUs: no reduction

Payment Calculation:
- Rank procedures by fee schedule amount
- Apply full payment to highest
- Apply reduction to subsequent
- Bilateral procedures: treated as two procedures

Modifier Impact:
- Modifier 51: Multiple procedures (informational for some carriers)
- Modifier 59: May allow bypass if distinct
- Modifier 50: Bilateral, subject to reduction
- Modifier XE/XS/XP/XU: May affect bundling but not MPPR

Documentation:
- Each procedure requires separate documentation
- Medical necessity for each procedure
- Distinct anatomic sites if claiming unbundled
- Time documentation for therapy MPPR""",
        "metadata": {
            "source": "CMS MPPR",
            "chapter": "Multiple Procedure",
            "topic": "Payment Reduction",
        },
    },
    # ============================================================
    # CATEGORY 3: COMPLIANCE & AUDITS (8 documents)
    # ============================================================
    {
        "content": """RAC and MAC Audit Process:
Understanding Medicare audit contractors and appeal processes.

Recovery Audit Contractors (RAC):
- Identify improper payments
- Review claims on contingency fee basis
- Can request medical records
- Automated and complex review authority

Medicare Administrative Contractors (MAC):
- Process and pay Medicare claims
- Conduct pre-payment and post-payment review
- Handle redeterminations (first level appeals)
- Issue LCDs

Audit Notification:
- Additional Documentation Request (ADR)
- Specific claim information
- Timeframe for response (typically 45 days)
- Records required to support services

Responding to Audits:
1. Verify legitimacy of request
2. Gather all relevant documentation
3. Organize records chronologically
4. Include cover letter summarizing services
5. Send via trackable method
6. Keep copies of everything submitted

Post-Audit Actions:
- Review determination letter carefully
- Note appeal deadlines
- Analyze patterns in denied claims
- Implement corrective action if warranted

Appeal Timeframes:
- Redetermination: 120 days from initial determination
- Reconsideration: 180 days from redetermination
- ALJ: 60 days from reconsideration
- Appeals Council: 60 days from ALJ
- Federal Court: 60 days from Appeals Council""",
        "metadata": {
            "source": "CMS Audits",
            "chapter": "RAC/MAC",
            "topic": "Audit Process",
        },
    },
    {
        "content": """ZPIC and UPIC Investigations:
Program integrity contractors have expanded authority for fraud investigations.

Zone Program Integrity Contractors (ZPIC) - Legacy:
- Transitioned to Unified Program Integrity Contractors (UPIC)
- Investigated potential fraud and abuse
- Could refer to OIG or DOJ

Unified Program Integrity Contractors (UPIC):
- Replaced ZPICs and PSCs
- Broader authority across Medicare and Medicaid
- Proactive data analysis
- Reactive complaint investigation

UPIC Authority:
- Prepayment and post-payment review
- Administrative actions (payment suspension)
- Referrals to law enforcement
- Revocation recommendations to CMS

Warning Signs of UPIC Investigation:
- Unusual ADR volume or scope
- Requests for policies and procedures
- Employee interviews requested
- Multiple claims across time periods reviewed

If Under Investigation:
1. Consult healthcare attorney immediately
2. Do not alter or destroy any records
3. Coordinate responses carefully
4. Consider voluntary disclosure if appropriate
5. Review billing practices for systemic issues

Payment Suspension:
- UPIC can recommend payment suspension
- Credible allegation of fraud required
- Applies during investigation
- Can be challenged through administrative process

Outcomes:
- No action (insufficient evidence)
- Overpayment demand
- Referral to OIG for exclusion
- Referral to DOJ for prosecution
- CMS enrollment revocation""",
        "metadata": {
            "source": "CMS Program Integrity",
            "chapter": "ZPIC/UPIC",
            "topic": "Fraud Investigation",
        },
    },
    {
        "content": """OIG Self-Disclosure Protocol:
Voluntary disclosure of potential fraud can mitigate penalties.

When to Consider Self-Disclosure:
- Discovery of potential fraud (not just overpayments)
- Billing irregularities with possible fraud implications
- Kickback concerns
- False claims submission
- Patterns suggesting intentional misconduct

Benefits of Self-Disclosure:
- Demonstrates good faith
- May reduce penalties
- Avoids exclusion in many cases
- Faster resolution than investigation
- Control over timing and narrative

Self-Disclosure Requirements:
1. Complete application to OIG
2. Detailed description of conduct
3. Time period involved
4. Financial assessment/damages
5. Corrective action plan
6. Supporting documentation

Financial Terms:
- Minimum settlement: 1.5× damages (vs 3× under FCA)
- OIG evaluates case specifics
- Compliance program considered
- Voluntary nature affects terms

Process Timeline:
- OIG acknowledges receipt
- Verification request possible
- Settlement negotiation
- Corporate Integrity Agreement may be required
- Payment terms established

What NOT to Self-Disclose:
- Mere overpayments (use different process)
- Issues without fraud element
- Matters already under investigation
- Claims outside OIG jurisdiction

Alternative: CMS Voluntary Refund:
- For overpayments without fraud
- 60-day rule for reporting/returning
- Different process than OIG disclosure""",
        "metadata": {
            "source": "OIG Disclosure",
            "chapter": "Self-Disclosure",
            "topic": "Voluntary Disclosure",
        },
    },
    {
        "content": """Corporate Compliance Program Elements:
Effective compliance programs have seven core elements.

Seven Elements of Effective Compliance:

1. Written Policies and Procedures:
   - Code of conduct
   - Specific compliance policies
   - Billing and coding policies
   - Regular updates required

2. Compliance Officer and Committee:
   - Designated compliance officer
   - Direct access to leadership
   - Compliance committee representation
   - Authority to implement changes

3. Training and Education:
   - Initial training for all employees
   - Role-specific training (billers, clinicians)
   - Annual refresher training
   - Documentation of attendance

4. Effective Lines of Communication:
   - Anonymous hotline/reporting mechanism
   - Non-retaliation policy
   - Open door policy
   - Regular compliance updates

5. Auditing and Monitoring:
   - Internal audits (routine and risk-based)
   - External audits periodically
   - Billing accuracy monitoring
   - Exclusion list screening

6. Enforcement Through Discipline:
   - Consistent discipline policy
   - Progressive discipline approach
   - Document all actions
   - Apply uniformly

7. Response to Issues:
   - Investigation protocols
   - Corrective action implementation
   - Root cause analysis
   - Prevent recurrence

Documentation:
- Maintain compliance files
- Meeting minutes
- Training records
- Audit reports and responses
- Investigation findings""",
        "metadata": {
            "source": "OIG Compliance",
            "chapter": "Compliance Programs",
            "topic": "Seven Elements",
        },
    },
    {
        "content": """Stark Law (Physician Self-Referral):
Prohibits referrals to entities with which physician has financial relationship.

Basic Prohibition:
A physician may not refer Medicare patients for designated health services (DHS)
to an entity with which the physician (or immediate family) has a financial
relationship, unless an exception applies.

Designated Health Services (DHS):
- Clinical laboratory services
- Physical therapy, occupational therapy, speech therapy
- Radiology and certain imaging
- Radiation therapy
- DME and supplies
- Parenteral and enteral nutrients
- Prosthetics, orthotics
- Home health services
- Outpatient prescription drugs
- Inpatient and outpatient hospital services

Financial Relationships:
- Ownership/investment interest
- Compensation arrangement (direct or indirect)
- Includes immediate family members

Key Exceptions:

In-Office Ancillary Services:
- Services furnished in same building
- Supervised by referring physician or group member
- Billed by physician or group

Fair Market Value:
- Compensation consistent with FMV
- Doesn't consider volume or value of referrals
- Commercially reasonable

Personal Services:
- Written agreement for at least 1 year
- Services specified
- FMV compensation
- Doesn't vary with referrals

Penalties:
- No Medicare payment for referred services
- Refund of amounts received
- Civil monetary penalties up to $15,000/service
- Exclusion from federal healthcare programs""",
        "metadata": {
            "source": "CMS Stark Law",
            "chapter": "Self-Referral",
            "topic": "Physician Self-Referral",
        },
    },
    {
        "content": """Anti-Kickback Statute (AKS):
Prohibits offering, paying, soliciting, or receiving remuneration for referrals.

Basic Prohibition:
It is illegal to knowingly and willfully offer, pay, solicit, or receive
any remuneration to induce or reward referrals of items or services
payable by a federal healthcare program.

Elements:
- Knowingly and willfully
- Offer, pay, solicit, or receive
- Remuneration (anything of value)
- Induce or reward referrals

Safe Harbors:
Safe harbors protect arrangements meeting all requirements:

Investment Interests:
- Small entities (<$50M)
- 60/40 investor rule
- No required referrals

Space Rental:
- Written agreement, at least 1 year
- Specifies premises
- Fair market value rent
- Aggregate space consistent with FMV

Equipment Rental:
- Similar to space rental
- FMV for equipment
- Commercially reasonable

Personal Services:
- Written agreement, at least 1 year
- Services specified
- FMV compensation
- Doesn't vary with referrals

Discounts:
- Properly disclosed
- Appropriately reflected in cost reports/claims
- Buyer earns rebate by meeting conditions

Penalties:
- Criminal: Up to $100,000 fine, 10 years imprisonment
- Civil: Up to $100,000 per violation, treble damages
- Exclusion from federal healthcare programs
- False Claims Act liability""",
        "metadata": {
            "source": "OIG AKS",
            "chapter": "Anti-Kickback",
            "topic": "Kickback Prohibition",
        },
    },
    {
        "content": """HIPAA Privacy and Security Requirements:
Healthcare entities must protect patient health information.

Protected Health Information (PHI):
- Individually identifiable health information
- Relates to health condition, treatment, or payment
- Transmitted or maintained in any form
- Includes electronic PHI (ePHI)

Permitted Uses and Disclosures:
- Treatment, payment, healthcare operations (TPO)
- With patient authorization
- To patient (right of access)
- As required by law
- For public health activities
- Abuse/neglect reporting

Patient Rights:
- Access to records
- Amendment of records
- Accounting of disclosures
- Request restrictions
- Confidential communications
- Breach notification

Minimum Necessary Standard:
- Limit PHI to minimum needed
- Applies to most disclosures
- Not applicable to treatment
- Role-based access policies

Security Rule Requirements:
- Administrative safeguards (policies, training)
- Physical safeguards (facility access, workstation security)
- Technical safeguards (access controls, encryption)
- Risk analysis required

Breach Notification:
- Notify affected individuals within 60 days
- Notify HHS (timing depends on size)
- Notify media if >500 affected in state
- Document all breaches (including small)

Penalties:
- Tier 1: $100-$50,000 per violation
- Tier 2: $1,000-$50,000 per violation
- Tier 3: $10,000-$50,000 per violation
- Tier 4: $50,000+ per violation
- Annual maximum varies by tier""",
        "metadata": {
            "source": "HHS HIPAA",
            "chapter": "Privacy/Security",
            "topic": "HIPAA Compliance",
        },
    },
    {
        "content": """Billing System Controls and Claim Scrubbing:
Effective billing systems include edit checks to prevent errors.

Pre-Billing Edits:
- Procedure/diagnosis code validation
- Modifier appropriateness
- Date of service validation
- Provider eligibility verification
- Patient eligibility verification

NCCI Edit Integration:
- Real-time PTP edit checking
- MUE unit verification
- Modifier override documentation
- Bundling rule application

LCD/NCD Compliance:
- Covered diagnosis code verification
- Frequency limitations
- Documentation requirements flagged
- Prior authorization alerts

Charge Description Master (CDM) Maintenance:
- Regular code updates
- Price review and updates
- Revenue code mapping
- Modifier defaults appropriately set
- Regular audits for accuracy

Claim Scrubber Functions:
- Missing information identification
- Code validation (valid codes, correct format)
- Edit rule application
- Duplicate claim detection
- Medical necessity screening

Quality Assurance Processes:
- Pre-bill review for high-risk claims
- Random sample audits
- Denial trend analysis
- Root cause correction
- Staff competency assessment

System Documentation:
- Edit library documentation
- Override authorization records
- Audit trail maintenance
- Policy basis for edit settings
- Regular edit effectiveness review""",
        "metadata": {
            "source": "Revenue Cycle",
            "chapter": "Billing Systems",
            "topic": "Claim Scrubbing",
        },
    },
    # ============================================================
    # CATEGORY 4: PRIOR AUTHORIZATION & APPEALS (6 documents)
    # ============================================================
    {
        "content": """Medicare Prior Authorization Requirements:
Certain services require approval before delivery.

Services Requiring Prior Authorization:
- Advanced diagnostic imaging (outpatient CT, MRI, PET)
- Non-emergency ambulance transportation
- Certain DME items (power wheelchairs, CPAP)
- Some surgical procedures
- Home health services (in some jurisdictions)
- Hyperbaric oxygen therapy
- Negative pressure wound therapy

Prior Authorization Process:
1. Submit PA request before service
2. Include clinical documentation
3. Await determination (typically 10 days)
4. Expedited review for urgent cases (72 hours)
5. Appeal if denied

Required Documentation:
- Patient demographics
- Clinical diagnosis and history
- Medical necessity statement
- Prior treatments tried
- Specific service requested
- Supporting clinical documentation

Timeframes:
- Standard: 10 business days
- Expedited: 72 hours (for urgent care)
- Review extension: Additional 14 days if needed

Post-Authorization:
- Service must match authorization
- Timeframes for service delivery
- Modification requests if needed
- Documentation retention requirements

Failure to Obtain PA:
- Claim will deny
- Cannot bill patient (if properly informed by Medicare)
- Retrospective review possible in emergencies
- Appeal process available""",
        "metadata": {
            "source": "CMS Prior Auth",
            "chapter": "Authorization",
            "topic": "Prior Authorization",
        },
    },
    {
        "content": """Advance Beneficiary Notice (ABN) Requirements:
ABNs notify patients when Medicare may not pay.

When ABN Required:
- Service may not be covered
- Service may exceed frequency limits
- Diagnosis may not support medical necessity
- Service may not be reasonable and necessary

ABN Form (CMS-R-131):
- Standard form required
- Proper completion mandatory
- Patient signature required
- Copy provided to patient

Required Elements:
- Patient and provider identification
- Item/service description (specific)
- Reason Medicare may not pay
- Estimated cost
- Patient choice options

Patient Options (Checkboxes):
- Option 1: Receive service, bill Medicare, accept financial responsibility if denied
- Option 2: Receive service, don't bill Medicare, patient pays
- Option 3: Don't receive service

Invalid ABN Issues:
- Blank ABN signed in advance
- No specific service listed
- No estimated cost
- Patient not given time to read
- Wrong patient signature
- Missing date

Consequences of Invalid ABN:
- Cannot bill patient for denied services
- Provider absorbs cost
- Potential compliance issues
- Pattern may trigger audit

Voluntary ABN:
- For Part B assigned claims
- Informs patient of potential cost
- Not required but recommended
- Different from mandatory ABN""",
        "metadata": {
            "source": "CMS ABN",
            "chapter": "Beneficiary Notice",
            "topic": "ABN Requirements",
        },
    },
    {
        "content": """Medicare Appeals Process Overview:
Five levels of appeal are available for claim denials.

Level 1: Redetermination (MAC):
- File within 120 days of initial determination
- Written request required
- Can submit additional documentation
- Decision within 60 days
- No minimum amount in controversy

Level 2: Reconsideration (QIC):
- File within 180 days of redetermination
- Qualified Independent Contractor reviews
- Can request on-the-record decision
- Decision within 60 days
- No minimum amount in controversy

Level 3: Administrative Law Judge (OMHA):
- File within 60 days of reconsideration
- Amount in controversy: $180 (2024)
- Can request hearing (in-person, video, telephone)
- Decision within 90 days
- Can be consolidated with related appeals

Level 4: Medicare Appeals Council:
- File within 60 days of ALJ decision
- Reviews ALJ decision
- May remand to ALJ
- Decision within 90 days
- No additional amount in controversy

Level 5: Federal District Court:
- File within 60 days of Appeals Council
- Amount in controversy: $1,800 (2024)
- Judicial review
- Longest timeframe

Tips for Successful Appeals:
- Meet all deadlines
- Provide complete documentation
- Cite relevant policies (LCD, NCD, NCCI)
- Address specific denial reasons
- Include clinical evidence of medical necessity""",
        "metadata": {
            "source": "CMS Appeals",
            "chapter": "Appeals Process",
            "topic": "Five Levels",
        },
    },
    {
        "content": """Redetermination Requests (Level 1 Appeals):
First level of Medicare appeal filed with the MAC.

Filing Requirements:
- Written request (form or letter)
- Within 120 days of initial determination
- Identify claim/services appealed
- Explain why determination is wrong
- Submit supporting documentation

Required Information:
- Beneficiary name and Medicare number
- Provider/supplier name and number
- Specific items/services appealed
- Dates of service
- Reasons for appeal

Supporting Documentation:
- Medical records (relevant portions)
- Physician orders
- Test results
- Progress notes
- Treatment plans
- Prior authorization (if applicable)

Cover Letter Should Include:
- Summary of case
- Specific reasons decision was wrong
- Citation of applicable policy (LCD/NCD)
- Request for specific outcome

Common Redetermination Issues:
- Medical necessity denials
- Coding errors
- Documentation deficiencies
- Frequency limits exceeded
- Coverage determination questions

Timeline:
- Submit: Within 120 days
- MAC decision: Within 60 days
- If unfavorable: 180 days to file reconsideration

Partially Favorable:
- Review decision carefully
- Can appeal remaining denied items
- Note specific items still at issue""",
        "metadata": {
            "source": "CMS Redetermination",
            "chapter": "Level 1",
            "topic": "Redetermination",
        },
    },
    {
        "content": """ALJ Hearing Preparation (Level 3 Appeals):
Administrative Law Judge hearings require thorough preparation.

Before the Hearing:
- Review entire case file
- Organize evidence chronologically
- Prepare witness testimony
- Draft opening statement
- Anticipate CMS arguments
- Know relevant LCDs/NCDs

Evidence Submission:
- All evidence should be in file before hearing
- Submit new evidence at least 5 days prior
- Explain why evidence wasn't available earlier
- Organize exhibits clearly
- Include exhibit list

Witness Preparation:
- Identify expert witnesses
- Prepare testimony outline
- Practice direct examination
- Anticipate cross-examination
- Confirm availability for hearing date

Hearing Process:
- Opening statements
- Presentation of evidence
- Witness testimony
- Cross-examination
- Closing arguments
- Questions from ALJ

Key Arguments:
- Medical necessity
- Standard of care
- Policy interpretation
- Documentation support
- Clinical evidence

Post-Hearing:
- Written brief (if permitted)
- Await decision (90 days)
- Review decision for appeals council
- Note deadline for Level 4

Virtual Hearings:
- Test technology beforehand
- Professional setting
- Documents readily accessible
- Backup phone connection""",
        "metadata": {
            "source": "OMHA ALJ",
            "chapter": "Level 3",
            "topic": "ALJ Hearings",
        },
    },
    {
        "content": """Medicare Appeals Council (Level 4 Appeals):
Departmental Appeals Board review of ALJ decisions.

When to Request Council Review:
- Disagree with ALJ decision
- ALJ made legal error
- ALJ decision inconsistent with CMS policy
- New evidence available (with good cause)

Filing Requirements:
- Written request
- Within 60 days of ALJ decision
- No additional amount in controversy
- Specify reasons for review

Request Should Include:
- Specific errors in ALJ decision
- Legal basis for appeal
- Relevant policy citations
- Statement of facts
- Requested outcome

Council's Authority:
- Review ALJ decision
- Issue new decision
- Remand to ALJ
- Dismiss request
- Decline review (for some cases)

Grounds for Remand:
- Incomplete record
- Procedural errors by ALJ
- New and material evidence
- Legal error requiring additional proceedings

Council Review Process:
- Reviews entire record
- No new hearing typically
- Written decision
- 90-day target (not binding)

Possible Outcomes:
- Affirm ALJ decision
- Reverse ALJ decision
- Modify ALJ decision
- Remand for new hearing
- Dismiss request

After Council Decision:
- 60 days to file in Federal District Court
- Amount in controversy: $1,800 (2024)
- Consider whether further appeal warranted""",
        "metadata": {
            "source": "DAB Appeals Council",
            "chapter": "Level 4",
            "topic": "Appeals Council",
        },
    },
    # ============================================================
    # CATEGORY 5: PAYMENT & FEE SCHEDULES (6 documents)
    # ============================================================
    {
        "content": """Medicare Physician Fee Schedule (MPFS) Payment Methodology:
Understanding how physician payments are calculated.

Payment Formula:
Payment = [(Work RVU × Work GPCI) + (PE RVU × PE GPCI) + (MP RVU × MP GPCI)] × CF

Components:
- Work RVU: Physician work (time, skill, intensity)
- PE RVU: Practice expense (overhead, supplies, staff)
- MP RVU: Malpractice expense (insurance cost)
- GPCI: Geographic Practice Cost Indices
- CF: Conversion Factor ($33.29 for 2024)

Work RVU Factors:
- Time to perform service
- Technical skill required
- Physical effort
- Mental effort and judgment
- Stress due to potential patient harm

Practice Expense:
- Facility (lower): Hospital, ASC
- Non-facility (higher): Office, clinic
- Includes staff, supplies, equipment

Geographic Adjustments (GPCI):
- Work: Physician labor costs by area
- PE: Practice expense costs by area
- MP: Malpractice premium costs by area

Payment Variations:
- Site of service affects payment
- Facility vs non-facility rates
- Global period implications
- Modifier impact

RVU Updates:
- Annual review by CMS
- RUC (AMA/Specialty) recommendations
- Budget neutrality requirements
- Misvalued code identification""",
        "metadata": {
            "source": "CMS MPFS",
            "chapter": "Payment Methodology",
            "topic": "Fee Schedule Calculation",
        },
    },
    {
        "content": """Facility vs Non-Facility Payment Rates:
Site of service significantly affects Medicare payment.

Definitions:
- Facility: Hospital (inpatient, outpatient), ASC
- Non-Facility: Physician office, independent clinic, patient home

Why Payment Differs:
- Facility: Hospital/ASC paid separately for overhead
- Non-facility: Physician payment includes practice expense
- PE RVU is lower for facility setting
- Work RVU and MP RVU unchanged by setting

Place of Service Codes:
- 11: Office
- 19: Off-campus hospital outpatient
- 21: Inpatient hospital
- 22: On-campus hospital outpatient
- 23: Emergency department
- 24: Ambulatory surgical center
- 31: Skilled nursing facility
- 32: Nursing facility

Payment Differential Examples:
- 99214 (office): Non-facility rate higher
- Procedures: Facility rate often lower for physician
- Some services: Same rate regardless of setting

Compliance Issues:
- Incorrect POS coding (intentional = fraud)
- Claiming non-facility when facility
- Not updating POS when service location changes
- Provider-based billing issues

Audit Red Flags:
- Pattern of non-facility POS from facility address
- High percentage of office visits from hospital-employed physicians
- POS inconsistent with service type""",
        "metadata": {
            "source": "CMS Site of Service",
            "chapter": "Facility/Non-Facility",
            "topic": "Payment Location",
        },
    },
    {
        "content": """Hospital Outpatient Prospective Payment System (OPPS):
Medicare payment for hospital outpatient services.

Payment Methodology:
- Ambulatory Payment Classifications (APCs)
- Services grouped by clinical similarity and cost
- Single payment rate per APC
- Includes most hospital costs for service

Status Indicators:
- A: Paid under fee schedule (not OPPS)
- C: Inpatient only
- J1: Hospital Part B drug, separate APC
- N: Packaged into other services
- Q1-Q4: Various packaging rules
- S: Significant procedure, separate APC
- T: Surgical procedure, multiple procedure reduction
- V: Clinic/ED visit, composite

Packaging:
- Minor services packaged into larger services
- Supplies, drugs (under threshold) packaged
- No separate payment for packaged items
- Packaging promotes efficiency

Composite APCs:
- Single payment for related services
- Encourages efficient care patterns
- ED visit + related services
- Clinic visit + related services

Pass-Through Payments:
- New technology devices
- New drugs (limited time)
- Transitional payments
- Eventually folded into APC rates

Outlier Payments:
- For unusually high-cost cases
- Cost threshold must be met
- Percentage of cost above threshold
- Protects against extreme cases""",
        "metadata": {
            "source": "CMS OPPS",
            "chapter": "Hospital Outpatient",
            "topic": "APC Payment",
        },
    },
    {
        "content": """Ambulatory Surgical Center (ASC) Payment System:
Medicare payment for surgical procedures in ASCs.

Covered Procedures:
- Procedures not requiring overnight stay
- Safety standards met
- CMS-approved ASC procedure list
- Not on inpatient-only list

Payment Components:
- ASC facility fee (includes most supplies, drugs)
- Physician professional fee (separate)
- Some devices paid separately
- Certain drugs paid separately

Payment Calculation:
- ASC payment = APC relative weight × ASC conversion factor
- Updated annually
- Some procedures have site-neutral payment

Covered Ancillary Services:
- Nursing, technician services
- Use of ASC facility
- Drugs and biologicals (most)
- Supplies and equipment
- Diagnostic and therapeutic items

Separately Payable Items:
- Certain implantable devices
- Certain high-cost drugs
- Pass-through devices (new technology)
- Brachytherapy sources

Quality Reporting:
- ASC Quality Reporting Program
- Measures for infection, falls, survey compliance
- Payment reduction for non-reporting
- Public reporting on Care Compare

Compliance Considerations:
- Only approved procedures
- Patient selection criteria
- Transfer agreements with hospitals
- Proper modifier usage
- Accurate coding""",
        "metadata": {
            "source": "CMS ASC",
            "chapter": "ASC Payment",
            "topic": "Surgery Center Payment",
        },
    },
    {
        "content": """Clinical Laboratory Fee Schedule (CLFS):
Medicare payment for clinical laboratory tests.

Payment Basis (PAMA):
- Protecting Access to Medicare Act (2014)
- Based on private payer rates
- Data collection from applicable labs
- Weighted median of private payer rates

Reporting Requirements:
- Applicable labs report private payer data
- Three-year data collection periods
- Rates phased in with caps on changes

Test Categories:
- Advanced Diagnostic Laboratory Tests (ADLTs)
- Clinical Diagnostic Laboratory Tests (CDLTs)
- New ADLT pricing methodology
- Market-based pricing

Panel Tests:
- Automated multichannel tests
- Cannot unbundle panel codes
- Individual tests if fewer performed
- Organ/disease panels

Specimen Collection:
- 36415: Venipuncture
- 36416: Capillary blood
- G0471: Collection in SNF
- Separate payment from test

Compliance Issues:
- Ordering unnecessary tests
- Unbundling panels
- Duplicate testing
- Billing for tests not performed
- Inappropriate referral arrangements

Medical Necessity:
- LCD diagnosis requirements
- Frequency limitations
- Documentation requirements
- Reflexive testing rules""",
        "metadata": {
            "source": "CMS CLFS",
            "chapter": "Laboratory",
            "topic": "Lab Fee Schedule",
        },
    },
    {
        "content": """Drug Reimbursement in Medicare Part B:
Payment for drugs and biologicals administered in medical settings.

Payment Methodology:
- Most drugs: Average Sales Price (ASP) + 6%
- Some drugs: Wholesale Acquisition Cost (WAC) + 6%
- New drugs without ASP data: WAC + 3%
- Blood products: Based on blood bank charges

ASP Calculation:
- Manufacturer reports ASP quarterly
- Includes discounts and rebates
- Does not include Medicaid rebates
- Updated quarterly by CMS

J-Code Billing:
- HCPCS J codes for most drugs
- Unit = specific dose (varies by drug)
- Bill actual units administered
- Wastage rules apply

Wastage Billing:
- Single-use vials: Bill unused portion with JW modifier
- Multi-use vials: Cannot bill wastage
- Document wastage amount
- Some carriers require documentation

340B Drug Pricing:
- Covered entities get discounted prices
- Medicare payment: ASP - 22.5%
- JG or TB modifier required
- Hospital outpatient and certain clinics

Sequestration:
- 2% payment reduction
- Applies to Medicare Part B drugs
- Separate from ASP calculation

Compliance Considerations:
- Accurate NDC documentation
- Correct unit billing
- Appropriate wastage claims
- 340B modifier compliance
- No duplicate billing (Medicare + patient)""",
        "metadata": {
            "source": "CMS Drug Payment",
            "chapter": "Part B Drugs",
            "topic": "Drug Reimbursement",
        },
    },
    # ============================================================
    # CATEGORY 6: DIAGNOSIS CODING & DOCUMENTATION (9 documents)
    # ============================================================
    {
        "content": """ICD-10-CM Official Coding Guidelines:
Understanding the conventions and rules for diagnosis coding.

Code Structure:
- 3-7 characters
- First character: Alpha (A-Z, except U)
- Characters 2-3: Numeric
- Characters 4-7: Alpha or numeric
- Decimal after 3rd character

General Coding Guidelines:
- Code to highest level of specificity
- Use combination codes when available
- Assign codes based on documentation
- Query physician when unclear
- Don't code suspected conditions as confirmed

Laterality:
- Required when applicable
- Right (1), Left (2), Bilateral (3)
- Unspecified only if not documented

7th Character Extensions:
- A: Initial encounter
- D: Subsequent encounter
- S: Sequela
- Specific meanings vary by code category
- Placeholder 'X' when needed

Sequencing Rules:
- Principal/first-listed diagnosis: Reason for encounter
- Secondary diagnoses: Coexisting conditions affecting care
- External cause codes: How/where injury occurred

Excludes Notes:
- Excludes1: Never code together
- Excludes2: Not included here, may be coded together
- Includes: Clarifies content
- Code also: Additional code may be needed
- Code first: Underlying condition first""",
        "metadata": {
            "source": "ICD-10-CM Guidelines",
            "chapter": "General Guidelines",
            "topic": "Coding Conventions",
        },
    },
    {
        "content": """Principal Diagnosis Selection:
Rules differ for inpatient vs outpatient settings.

Inpatient Principal Diagnosis:
- Condition established after study
- Chiefly responsible for admission
- May differ from admitting diagnosis
- Based on discharge summary

Outpatient First-Listed Diagnosis:
- Reason for encounter/visit
- What brought patient to provider
- May be symptom if diagnosis not confirmed
- Do not code uncertain diagnoses as confirmed

Two or More Conditions Equally Meet Definition:
- Either may be sequenced first
- Circumstances of admission may guide
- Payer preference may apply

Symptoms with Related Definitive Diagnosis:
- Code definitive diagnosis, not symptoms
- Unless symptom not routinely associated
- Document both if symptom unusual for diagnosis

Suspected/Probable/Rule Out:
- Inpatient: Code as if confirmed
- Outpatient: Code symptoms/signs only
- Different rules for different settings

Complications of Care:
- Code complication when documented
- Requires causal relationship
- Provider must document relationship
- Query if unclear

Admission from Observation/ED:
- Principal diagnosis: Reason for inpatient admission
- May differ from observation reason
- Document evolution of condition""",
        "metadata": {
            "source": "ICD-10-CM Guidelines",
            "chapter": "Principal Diagnosis",
            "topic": "Diagnosis Selection",
        },
    },
    {
        "content": """Secondary Diagnosis Coding:
Additional diagnoses that affect patient care or resource utilization.

When to Code Secondary Diagnoses:
- Clinical evaluation performed
- Therapeutic treatment given
- Diagnostic procedures performed
- Extended length of stay/increased care
- Requires additional nursing/monitoring

Chronic Conditions:
- Code if managed or monitored
- Document relevance to encounter
- Ongoing medications support coding
- May affect treatment decisions

Acute vs Chronic:
- Both may be coded if applicable
- Acute sequenced before chronic (usually)
- Document relationship if relevant

Complications and Comorbidities:
- Affect severity of illness
- Impact resource utilization
- Must be documented by provider
- Query for clarification if needed

Personal History (Z85-Z87):
- Previous condition no longer present
- Affects current treatment decisions
- Family history also relevant

Status Codes (Z93-Z99):
- Presence of devices/conditions
- Transplant, ostomy, dependence on devices
- Affect care planning

Social Determinants (Z55-Z65):
- Housing, employment, education issues
- May affect treatment/compliance
- Document based on assessment
- Impact care management""",
        "metadata": {
            "source": "ICD-10-CM Guidelines",
            "chapter": "Secondary Diagnosis",
            "topic": "Additional Diagnoses",
        },
    },
    {
        "content": """Present on Admission (POA) Indicators:
Required for inpatient claims to identify conditions present at admission.

POA Indicator Values:
- Y: Yes, present at admission
- N: No, not present at admission
- U: Documentation insufficient
- W: Clinically undetermined
- 1: Exempt from POA reporting

Hospital-Acquired Conditions (HAC):
- Selected conditions not POA
- Higher cost/resource utilization
- Payment implications if not POA
- Quality measure reporting

HAC Categories Include:
- Foreign object retained after surgery
- Air embolism
- Blood incompatibility
- Catheter-associated UTI
- Vascular catheter-associated infection
- Certain falls and trauma
- Manifestations of poor glycemic control
- Surgical site infections
- DVT/PE after certain surgeries
- Pressure ulcers stage III and IV

Documentation Requirements:
- Timing of condition development
- Clear statement of POA status
- Clinical findings supporting POA
- Query physician if unclear

Compliance Considerations:
- Accurate POA reporting
- Complete documentation
- Query process for unclear cases
- Audit and monitor accuracy
- Staff education on POA guidelines""",
        "metadata": {
            "source": "CMS POA",
            "chapter": "Present on Admission",
            "topic": "HAC Reporting",
        },
    },
    {
        "content": """Hierarchical Condition Categories (HCC) and Risk Adjustment:
HCCs affect Medicare Advantage payment through risk adjustment.

Risk Adjustment Basics:
- Adjusts capitation payment for patient health status
- Sicker patients = higher payment
- Healthier patients = lower payment
- Based on diagnosis codes submitted

HCC Categories:
- Diagnostic categories with cost implications
- Based on ICD-10-CM codes
- Hierarchical: Higher severity captures lower
- Annual model updates

Documentation Requirements:
- Must reflect current clinical status
- Face-to-face encounters required
- Assessment and plan documented
- Supporting clinical findings
- Specific, codeable diagnoses

High-Risk Codes:
- Diabetes with complications
- Heart failure
- Chronic kidney disease
- COPD
- Major depressive disorder
- Vascular disease

Audit Vulnerability:
- RADV audits (Risk Adjustment Data Validation)
- Medical record must support code
- Signature, credentials, date required
- Diagnosis must affect treatment plan

Compliance Best Practices:
- Don't code based solely on prior claims
- Document all chronic conditions managed
- Annual assessments for ongoing conditions
- Query for specificity
- Accurate code assignment

Common Errors:
- Coding unconfirmed diagnoses
- Missing specificity (HCC not captured)
- No documentation of current management
- Coding from problem list without assessment""",
        "metadata": {
            "source": "CMS Risk Adjustment",
            "chapter": "HCC",
            "topic": "Risk Adjustment Coding",
        },
    },
    {
        "content": """Z Codes: Factors Influencing Health Status:
Z codes capture reasons for encounters and health status information.

Categories of Z Codes:
- Z00-Z13: Encounters for examinations
- Z14-Z15: Genetic carrier and susceptibility
- Z16: Resistance to antimicrobial drugs
- Z17: Estrogen receptor status
- Z18: Retained foreign body fragments
- Z20-Z29: Contact/exposure, prophylactic measures
- Z30-Z39: Reproductive, pregnancy
- Z40-Z53: Encounters for specific care
- Z55-Z65: Socioeconomic/psychosocial
- Z66: DNR status
- Z67: Blood type
- Z68: BMI
- Z69-Z76: Other circumstances
- Z77-Z99: Status codes

When Z Codes Can Be Principal:
- Z00-Z04: Examination encounters
- Z23: Immunization
- Z30-Z39: Reproductive
- Z40-Z53: Specific care (chemo, dialysis)

When Z Codes Are Secondary:
- Z codes describing status/history
- BMI (requires obesity/overweight)
- Blood type
- External cause circumstances

Documentation Tips:
- Document reason for screening
- Specify type of history
- Current vs resolved conditions
- Family member relationship for family history

Common Compliance Issues:
- Missing obesity for BMI coding
- Screening without documented indication
- History codes for active conditions
- Missing specificity in status codes""",
        "metadata": {
            "source": "ICD-10-CM Guidelines",
            "chapter": "Z Codes",
            "topic": "Health Status Factors",
        },
    },
    {
        "content": """External Cause Codes:
Codes describing how injury occurred, place, and activity.

External Cause Categories:
- V00-V99: Transport accidents
- W00-X58: Other external causes of injury
- X71-X83: Intentional self-harm
- X92-Y09: Assault
- Y21-Y33: Event of undetermined intent
- Y35-Y38: Legal intervention, war
- Y62-Y84: Complications of medical care
- Y90-Y99: Supplementary factors

Code Selection Guidelines:
- Code for each cause if multiple injuries
- Code most serious cause first
- Include all relevant codes
- Capture activity and place

Place of Occurrence (Y92):
- Where injury occurred
- Home, school, workplace categories
- Specific locations within categories
- Important for injury surveillance

Activity (Y93):
- What patient was doing when injured
- Sports, leisure, work activities
- Specific activity types
- Supports injury analysis

External Cause Status (Y99):
- Employment status at time of injury
- Civilian activity
- Military activity
- Student/volunteer

Sequencing:
- External cause codes are secondary
- Never principal/first-listed
- Follow injury code sequencing rules
- May use multiple external cause codes

Documentation Requirements:
- Describe mechanism of injury
- Location where occurred
- Activity during injury
- Civilian vs military context""",
        "metadata": {
            "source": "ICD-10-CM Guidelines",
            "chapter": "External Cause",
            "topic": "Injury Circumstances",
        },
    },
    {
        "content": """Social Determinants of Health (SDOH) Coding:
Z codes capturing socioeconomic factors affecting health.

SDOH Categories (Z55-Z65):
- Z55: Problems related to education/literacy
- Z56: Employment/unemployment problems
- Z57: Occupational exposure to risk factors
- Z58: Physical environment problems
- Z59: Housing and economic circumstances
- Z60: Social environment problems
- Z62: Problems related to upbringing
- Z63: Family circumstances problems
- Z64: Problems with certain circumstances
- Z65: Problems related to other circumstances

Documentation Requirements:
- Must be documented by provider
- Based on patient screening/assessment
- Relevant to current care episode
- Affects treatment or resource needs

Screening Tools:
- PRAPARE (Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences)
- AHC (Accountable Health Communities) HRSN
- IHELP (Income, Housing, Education, Legal, Personal)
- Custom organizational screens

Code Assignment:
- Assign based on documented assessment
- Patient self-report acceptable
- Query provider if unclear
- Secondary diagnosis typically

Impact on Care:
- Affects care coordination
- Identifies resource needs
- Risk stratification
- Quality measure reporting

Value-Based Care Relevance:
- Population health management
- Care gap identification
- Resource allocation
- Health equity analysis""",
        "metadata": {
            "source": "ICD-10-CM Guidelines",
            "chapter": "SDOH",
            "topic": "Social Determinants",
        },
    },
    {
        "content": """Medical Necessity and ICD-10 to CPT Linkage:
Establishing the relationship between diagnosis and procedure.

Medical Necessity Defined:
- Service is reasonable for diagnosis/symptoms
- Appropriate in terms of medical practice
- Rendered at appropriate setting/level
- Not primarily for convenience

Documentation Elements:
- Chief complaint and symptoms
- Clinical findings supporting diagnosis
- Rationale for service ordered
- Expected outcome of treatment

ICD-10 to CPT Relationships:
- LCDs specify covered diagnoses
- NCDs may specify coverage requirements
- Some procedures require specific diagnoses
- Clinical indication must match service

LCD Compliance:
- Review covered diagnosis list
- Ensure code specificity meets requirements
- Document supporting clinical findings
- Frequency limitations by diagnosis

Red Flags for Audit:
- High-specificity procedure, low-specificity diagnosis
- Diagnosis doesn't support service
- Pattern of same diagnosis across different services
- Diagnosis changed to match procedure

Best Practices:
- Code to highest specificity documented
- Ensure diagnosis supports medical necessity
- Document clinical rationale
- Query if diagnosis unclear
- Review LCD requirements before ordering

Appeals Based on Medical Necessity:
- Include clinical documentation
- Cite relevant guidelines
- Explain clinical rationale
- Reference standard of care
- Provide supporting literature if appropriate""",
        "metadata": {
            "source": "CMS Medical Necessity",
            "chapter": "Documentation",
            "topic": "ICD-10/CPT Linkage",
        },
    },
]


def seed_chromadb(skip_validation: bool = False) -> dict:
    """Seed the ChromaDB with sample policy documents.

    Args:
        skip_validation: If True, skip policy validation (faster but less safe)

    Returns:
        Dictionary with performance metrics
    """
    metrics = {
        "document_count": len(SAMPLE_POLICIES),
        "validation_time_ms": 0,
        "embedding_time_ms": 0,
        "total_time_ms": 0,
        "validation_passed": True,
    }

    total_start = time.time()

    # Validate policies before seeding
    if not skip_validation:
        print("Validating policy documents...")
        validation_start = time.time()
        is_valid, errors = validate_policies(SAMPLE_POLICIES)
        metrics["validation_time_ms"] = round(
            (time.time() - validation_start) * 1000, 2
        )

        if not is_valid:
            print("Validation FAILED:")
            for error in errors:
                print(f"  - {error}")
            metrics["validation_passed"] = False
            return metrics
        print(f"Validation passed ({metrics['validation_time_ms']}ms)")

    print("Initializing ChromaDB...")
    store = ChromaStore(persist_dir="./data/chroma", collection_name="policies")

    print(f"Current document count: {store.count()}")

    if store.count() > 0:
        print("Clearing existing documents...")
        store.clear()

    print(f"Adding {len(SAMPLE_POLICIES)} policy documents...")

    # Add effective_date and last_reviewed to metadata
    documents = [p["content"] for p in SAMPLE_POLICIES]
    metadatas = []
    for p in SAMPLE_POLICIES:
        metadata = p["metadata"].copy()
        metadata["effective_date"] = POLICY_EFFECTIVE_DATE
        metadata["last_reviewed"] = LAST_REVIEWED_DATE
        metadatas.append(metadata)
    ids = [f"policy_{i}" for i in range(len(SAMPLE_POLICIES))]

    # Benchmark embedding/storage
    embedding_start = time.time()
    store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
    metrics["embedding_time_ms"] = round((time.time() - embedding_start) * 1000, 2)

    metrics["total_time_ms"] = round((time.time() - total_start) * 1000, 2)

    print(f"Done! Total documents: {store.count()}")
    print("\nPerformance Metrics:")
    print(f"  - Documents: {metrics['document_count']}")
    print(f"  - Validation: {metrics['validation_time_ms']}ms")
    print(f"  - Embedding/Storage: {metrics['embedding_time_ms']}ms")
    print(f"  - Total Time: {metrics['total_time_ms']}ms")

    # Test search with timing
    print("\nTesting search...")
    search_start = time.time()
    results = store.search("NCCI PTP edits billing", n_results=2)
    search_time = round((time.time() - search_start) * 1000, 2)
    print(f"Search completed in {search_time}ms")
    for r in results:
        print(f"  - {r['metadata'].get('topic', 'Unknown')}: {r['content'][:100]}...")

    return metrics


if __name__ == "__main__":
    seed_chromadb()
