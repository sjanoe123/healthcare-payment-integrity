## NCCI Edits & Policy Manuals — Ingestion Blueprint

### 1. Scope & Source Inventory
| Dataset | Description | Format | Official Source |
| --- | --- | --- | --- |
| **PTP Edit Tables** | Columnar files listing mutually exclusive CPT/HCPCS code pairs | CSV/TXT inside quarterly ZIP | CMS NCCI release page (https://www.cms.gov/Medicare/Coding/NationalCorrectCodInitEd/NCCI-Coding-Edits) |
| **MUE Tables** | Medically Unlikely Edits with quantity limits per code | CSV/TXT inside quarterly ZIP | Same as above |
| **PTP Policy Manual** | Narrative rationale for PTP edits | PDF per chapter (Intro + Chapters 1–13) | CMS (https://www.cms.gov/Medicare/Coding/NationalCorrectCodInitEd/Downloads) |
| **MUE Policy Manual** | Policy statements supporting MUE limits | PDF per chapter | CMS site |
| **Historical Archive** | Prior releases for trend/debug | CMS archives | same |

All assets are ingested **every quarter** (CMS publishes January 1, April 1, July 1, October 1). Historical versions retained for delta analysis.

### 2. Storage Layout & Environments
- **Raw bucket**: `s3://pi-${stage}-ncci-raw/<release>/[ptp|mue|manual]/...` (stores original ZIP/PDF + manifest JSON).
- **Processed bucket**: `s3://pi-${stage}-ncci-processed/<release>/...` for normalized JSON/Parquet exports and Docling chunk outputs (manuals).
- **DynamoDB tables**:
  - `ncci_ptp_pairs` (partition: `code_primary`, sort: `code_secondary#release`).
  - `ncci_mue_limits` (partition: `code`, sort: `release`).
- **Glue Catalog** views for Athena/Spectrum analytics and Bedrock KB ingestion staging.
- **Hash table**: DynamoDB `ncci_release_hashes` to detect new uploads via SHA256.

### 3. Ingestion Pipeline
1. **Quarterly Release Detection**
   - EventBridge schedule `cron(0 5 1 1,4,7,10 ? *)` triggers `ncci-release-checker` Lambda.
   - Lambda scrapes CMS metadata JSON (or HTML + regex) to compare `release_version` vs Dynamo hash table; if new, publish `NewNCCIRelease` event (SNS + EventBridge bus) with payload `{ release_id, urls[] }`.
2. **Download & Raw Staging**
   - Step Functions workflow `NCCIIngestionWorkflow` orchestrates parallel download tasks for PTP, MUE, manuals.
   - Each download Lambda streams ZIP/PDF to raw bucket, writes manifest (`release_id`, `source_url`, `sha256`, `files[]`).
3. **Processing Stage**
   - **PTP Processor Lambda**
     - Unzips CSV, normalizes column headers, enforces schema (see metadata section).
     - Validates row counts, ensures `code_primary != code_secondary`, verifies modifier indicators within {0,1,9}.
     - Writes Parquet chunks to processed bucket and upserts DynamoDB entries.
   - **MUE Processor Lambda**
     - Similar flow: parse CSV, enforce numeric types, cross-check units of service.
   - **Manual Processor (Docling)**
     - Converts PDF chapters to structured JSON (section headings, rationale paragraphs, examples).
     - Splits into 800–1,000 token chunks with overlap for RAG; pushes to processed bucket.
4. **Metadata Enrichment & KB Sync**
   - Step Functions job aggregates processed outputs per dataset, adds release metadata (effective quarter, CMS change request IDs) and writes to Glue tables.
   - Daily `NCCIKBSync` Step Function packages new manual chunks + annotated edit records into Bedrock KB datasets with structured tags.
5. **Observability & Alerts**
   - CloudWatch metrics: `NCCIReleaseDetected`, `PTPRowsProcessed`, `MUERowsProcessed`, `ManualChunksCreated`, `KBUpserts`, `ValidationFailures`.
   - SNS notifications for validation failures or CMS download errors.
6. **Retention & Compliance**
   - Raw ZIP/PDF kept 10 years (aligns with audit retention for code sets).
   - Processed Parquet/JSON kept 5 years; manual chunks 3 years.
   - Access logging + encryption enforced on both buckets; no PHI expected.

### 4. Dataset-Specific Metadata Schemas
#### 4.1 PTP Edit Records
| Field | Description |
| --- | --- |
| `release_id` | e.g., `2025Q1` |
| `code_primary` | HCPCS/CPT primary code |
| `code_secondary` | Secondary code |
| `modifier_indicator` | 0 (no modifiers bypass), 1 (modifier may bypass), 9 (not applicable) |
| `edit_effective_date` / `edit_termination_date` | Dates from CMS file |
| `edit_type` | Column from CMS (e.g., “Column1/Column2” ) |
| `policy_reference` | Chapter/section pointer (linked to manual metadata) |
| `facility_indicator` / `professional_indicator` | Derived from CMS columns |
| `change_indicator` | New, revised, or unchanged vs prior release |
| `cms_change_request` | If provided in release notes |
| `fraud_risk_signal` | Derived tag (e.g., “likely upcoding guardrail”) for RAG |
| `documentation_requirements` | If manual references specific documentation |

#### 4.2 MUE Records
| Field | Description |
| --- | --- |
| `release_id` |
| `code` |
| `mue_value` | Integer limit |
| `mue_adjudication_indicator` | 1 (claim line), 2 (date of service), 3 (per control number) |
| `units_of_service` | Derived description |
| `effective_date` / `termination_date` |
| `rationale_category` | Manual-derived rationale (e.g., anatomical, clinical) |
| `modifier_applicability` | Whether modifiers can influence quantity |
| `documentation_guidance` | Excerpts from manual for FWA rules |

#### 4.3 Policy Manuals (PTP & MUE)
| Field | Description |
| --- | --- |
| `release_id` |
| `chapter` / `section` |
| `code_range` | Code(s) discussed |
| `clinical_context` | Indications/contraindications described |
| `billing_examples` | Example scenarios |
| `modifier_guidance` | Specific instructions |
| `fraud_indicators` | Highlighted schemes |
| `documentation_requirements` |
| `mac_specific_rule` | Boolean + list of jurisdictions |
| `chunk_text` | Body text for RAG |
| `source_url` / `page_number` |

### 5. Validation & QA Gates
- **Schema validation**: Great Expectations suite applied to normalized Parquet files (type checks, allowed value sets, null constraints).
- **Record count diff**: Compare total PTP/MUE rows vs prior release; threshold alerts if deviations >5% unless explained in release notes.
- **Change logs**: Generate CSV + JSON diffs (`new_pairs.csv`, `retired_pairs.csv`, `mue_changes.csv`) stored under processed bucket and pushed to SIU Slack.
- **Manual cross-links**: Automated job ensures every `policy_reference` in edit tables matches a manual chunk; missing links flagged.
- **Unit tests**: Pytest suite mocking CMS files verifying parsing logic, Dynamo upsert, KB payload structure.

### 6. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Build release detector + raw download staging + hash tracking |
| Week 2 | Implement PTP parser (CSV→Parquet + Dynamo) with validation + diff reports |
| Week 3 | Implement MUE parser + diff reports; integrate manual Docling pipeline |
| Week 4 | Glue catalog definitions, Bedrock KB sync, observability wiring |
| Ongoing | Quarterly release ingestion, weekly smoke test (download sample file ensure pipeline ready) |

### 7. Open Items / Clarifications
- Confirm whether to expose NCCI data via API Gateway for downstream services or rely on Dynamo/Athena only.
- Determine if certain specialist rules (e.g., anesthesia edits) need custom tagging beyond standard metadata.
- Validate whether manual PDFs ever contain restricted distribution content (none expected, but confirm with Compliance).
