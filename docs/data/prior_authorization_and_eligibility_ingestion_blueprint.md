## Prior Authorization & Eligibility Data — Ingestion Blueprint

### 1. Scope & Source Inventory
| Dataset Category | Examples | Format | Source |
| --- | --- | --- | --- |
| **National Standards** | X12 270/271 (eligibility), 278 (PA request/response), HL7 FHIR CoverageEligibility, Da Vinci PAS IG | EDI (X12), JSON/XML (FHIR) | X12 specs, HL7 Da Vinci guides |
| **Payer PA Policies & Criteria** | CMS Prior Authorization lists, MAC articles, commercial plan PA matrices (e.g., UHC, Anthem, Aetna) | PDF/HTML/XLS | CMS, payer portals, plan bulletins |
| **Plan Formularies & Step Therapy Rules** | Part D formulary files, state Medicaid preferred drug lists, payer-specific criteria | CSV/PDF | CMS Formulary Reference, state Medicaid sites |
| **Eligibility & Benefits Reference** | Benefit plan coverage tables, MOOP, co-pay tiers | CSV/JSON | Payer APIs (FHIR Coverage), SBC PDFs |
| **Utilization Management Vendor Criteria** | MCG/InterQual summaries accessible via payer proxy (e.g., QualCare IPA, Medicaid medical policies) | PDF | Public payer sites |
| **Appeals/Denial Reason Codes** | CARC/RARC, payer-specific denial reason matrices | CSV/XLS | CMS, CAQH CORE, payer documentation |

### 2. Storage Layout & Cadence
- **Raw**: `s3://pi-${stage}-paelig-raw/<category>/<source>/<yyyy>/<mm>/...` (retain original EDI, PDF, XLS, JSON).
- **Processed**: `s3://pi-${stage}-paelig-processed/<category>/<release>/...` (normalized JSON/Parquet + Docling chunks).
- **Cadence**
  - Eligibility standards (X12/FHIR IGs): monitor semi-annual updates (June/December) + ad hoc errata.
  - CMS PA lists & MAC bulletins: monthly check.
  - Commercial payer PA matrices + formularies: monthly for major nationals, quarterly for regionals.
  - State Medicaid preferred drug lists: monthly diff.
  - CARC/RARC codes: quarterly per CMS release.

### 3. Pipeline Strategy
1. **Acquisition Layer**
   - EventBridge schedules per category; Step Function orchestrates download jobs.
   - X12 specs/manuals pulled from X12 storefront (licensed) or cached copy; Da Vinci PAS/FHIR from HL7 Confluence (requires login) → manual upload support.
   - CMS PA lists + payer policies scraped via authenticated HTTP (headers stored in Secrets Manager).
   - Formularies ingested via CMS Formulary Reference File (zip) + state PDF/CSV downloads.
   - CARC/RARC matrices downloaded from CMS (CSV) + CAQH CORE.
2. **Processing Layer**
   - **EDI Parsers**: use existing X12 parsing library to convert 270/271/278 examples into structured JSON for reference scenarios (segments, loops, codes).
   - **Policy Doc Processing**: Docling PDF/HTML → JSON sections capturing service, CPT/HCPCS list, criteria, required documentation, turnaround times.
   - **Formulary Normalizer**: parse CMS Part D and Medicaid lists into schema (drug, tier, PA required, step therapy requirements, quantity limits).
   - **Eligibility Benefit Tables**: convert payer CSV/XLS to normalized schema (plan, benefit category, prior auth requirement flag, limit values).
3. **Metadata Enrichment**
   - Link CPT/HCPCS/ICD codes to code reference dataset.
   - Map payer policies to payer taxonomy (NAIC code, region, product type, line of business).
   - Tag requirement type (PA, notification, step therapy, quantity limit).
4. **Catalog & Access**
   - Glue tables: `pa_policy_rules`, `eligibility_benefits`, `formulary_rules`, `pa_standards`, `denial_codes`.
   - Dynamo table `pa_requirements_latest` keyed by `payer#service_code` for fast lookup.
5. **Bedrock KB Sync**
   - Chunk textual criteria (decision trees, documentation requirements) with metadata: payer, service, code list, clinical condition, turnaround time, appeal contact.
6. **Alerting & Reporting**
   - After each ingestion run, post summary (new policies, retired policies, formulary changes) to Claims Ops/SIU Slack.
   - Generate diff files: `pa_new_rules.json`, `pa_changed_rules.json`, `formulary_changes.json`.

### 4. Metadata Schemas
#### PA Policy Rule (per service/payer)
| Field | Description |
| --- | --- |
| `payer_id` / `payer_name` |
| `product_type` | Medicare Advantage, Commercial PPO, Medicaid, etc. |
| `service_category` | Imaging, Surgery, DME, Pharmacy |
| `cpt_hcpcs_codes` |
| `diagnosis_codes` (if specified) |
| `pa_required` | true/false |
| `criteria_summary` | text chunk |
| `documentation_requirements` | list |
| `clinical_guideline_refs` | references to MCG/InterQual/Choosing Wisely |
| `turnaround_time` |
| `submission_channel` | Portal, Fax, API |
| `effective_date` / `expiry_date` |
| `jurisdiction` / `state` |
| `source_url` / `retrieved_at` |

#### Eligibility & Benefit Table
| Field | Description |
| --- | --- |
| `payer_id` |
| `plan_id` / `plan_name` |
| `benefit_category` (e.g., inpatient, outpatient imaging) |
| `coverage_limit` | dollar/visit limit |
| `pa_flag` | yes/no |
| `referral_required` |
| `coinsurance` / `copay` |
| `oop_max` |
| `notes` |

#### Formulary Rule
| Field | Description |
| --- | --- |
| `drug_name` / `ndc` |
| `tier` |
| `pa_required` |
| `step_therapy` |
| `quantity_limit` |
| `exception_process` |
| `plan_id` |

#### Denial Reason Codes (CARC/RARC)
| Field | Description |
| --- | --- |
| `code` |
| `description` |
| `category` (eligibility, medical necessity, PA missing) |
| `mapping_to_pa_rule` | derived link |

### 5. Validation & QA
- Schema validation for each normalized dataset (Great Expectations suites).
- Cross-check payer policy counts vs previous month (threshold ±10%).
- Ensure each `pa_policy_rule` references valid codes.
- Verify formulary file row counts vs CMS published totals.
- Sample manual QA: compare parsed criteria text to source PDF for top services.

### 6. Observability
- Metrics: `PAFilesDownloaded`, `PoliciesProcessed`, `FormularyRowsProcessed`, `EligibilityRecords`, `DiffAlerts`, `ValidationFailures`.
- Dashboards: show ingestion latency, policy change counts per payer, top impacted service categories.
- Alerts for download failures, schema validation failures, or significant policy swings.

### 7. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Build acquisition jobs for CMS PA lists, payer policy portals, formulary downloads |
| Week 2 | Implement Docling + parser pipeline for policy PDFs, Great Expectations suites |
| Week 3 | Normalize eligibility tables, CARC/RARC codes, integrate Dynamo/Glue |
| Week 4 | Build diff reporting, Bedrock KB sync, alerting, and dashboards |
| Ongoing | Monthly ingestion, quarterly standard updates, manual overrides for urgent payer changes |

### 8. Open Questions
- Confirm list of priority commercial payers and whether automated login (MFA) is required for their PA portals.
- Determine licensing/usage rules for MCG/InterQual content beyond publicly posted summaries.
- Decide retention policy for payer PDFs (recommend 7 years raw, 3 years processed).
