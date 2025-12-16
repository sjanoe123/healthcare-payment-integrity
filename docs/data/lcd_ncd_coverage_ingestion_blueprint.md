## LCD / NCD Coverage Determinations & Articles — Ingestion Blueprint

### 1. Scope & Source Inventory
| Dataset | Description | Format | Source |
| --- | --- | --- | --- |
| **LCD Master File** | All Local Coverage Determinations (active + retired) | JSON via CMS LCD API (https://www.cms.gov/medicare-coverage-database/services/lcd-download.aspx) | Includes LCD ID, jurisdiction (MAC), status, effective dates |
| **LCD Articles** | Companion articles / FAQs linked to LCDs | JSON via LCD Article API + PDF attachments | Provide coding, documentation, education guidance |
| **NCD Master File** | National Coverage Determinations | XML/CSV + PDF | CMS NCD database |
| **NCD Decision Memos & Implementation Articles** | Supporting documents for NCD updates | PDF/HTML | CMS NCD portal |
| **Retired LCD/NCD Archive** | Historical versions for audit | Same as above | Need retention |

All datasets ingested in full (active + retired) to enable historical comparisons.

### 2. Storage Layout & Cadence
- **Buckets**:
  - Raw: `s3://pi-${stage}-coverage-raw/{lcd|ncd}/{release_date}/...` (JSON/XML + PDFs).
  - Processed: `s3://pi-${stage}-coverage-processed/{lcd|ncd}/{release_date}/...` (normalized Parquet + chunked text).
- **Cadence**
  - **Daily**: Incremental LCD/LCD-Article pulls (API filters `lastUpdated >= yesterday`).
  - **Weekly**: NCD diff check (API exports less frequent).
  - **Monthly**: Full re-sync to catch backfilled adjustments.
  - Alerts on each successful sync summarizing new/changed/retired policies.

### 3. Pipeline Strategy
1. **Incremental Fetch Lambdas**
   - LCD fetcher queries API with pagination; stores raw JSON responses + PDF attachments.
   - Article fetcher pulls linked articles per LCD ID; downloads attachments.
   - NCD fetcher ingests XML/CSV master file + downloads decision memos.
   - Metadata (hash, timestamp) recorded in DynamoDB `coverage_ingestion_meta`.
2. **Processing & Normalization**
   - **LCD Normalizer**
     - Flattens JSON into canonical schema (see metadata section), expands arrays (diagnosis codes, procedure codes, indications).
     - Produces Parquet files partitioned by `lcd_id` + `effective_year`.
   - **Article Processor**
     - Parses PDF attachments via Docling; extracts coding guidance, documentation requirements, billing modifiers.
     - Links `article_id` → `lcd_id`.
   - **NCD Processor**
     - Similar normalization for coverage/limitations; Docling chunking for decision memos.
3. **Metadata Enrichment**
   - Join LCDs to MAC table (jurisdiction to region, state list) using crosswalk from Planning doc (Implementation Unlock Plan §15).
   - Enrich with `specialty`, `benefit_category`, `diagnosis_group` derived from CMS taxonomy.
4. **Glue / Athena / Dynamo**
   - Glue tables: `lcd_policies`, `lcd_articles`, `ncd_policies`, `ncd_memos`.
   - Optional Dynamo tables for fast lookups (`lcd_metadata`, `ncd_metadata`), keyed by `policy_id`.
5. **Bedrock KB Sync**
   - Coverage textual chunks (indications, limitations, documentation requirements, coding guidance) synced daily to KB with metadata tags.
6. **Alerting**
   - After each ingestion run, Step Function posts summary to Slack/Teams: counts of new/updated/retired LCDs, MACs affected, notable status changes.

### 4. Metadata Schema
#### 4.1 LCD Policies (structured record)
| Field | Description |
| --- | --- |
| `lcd_id` | e.g., L12345 |
| `title` | LCD title |
| `status` | Draft, Final, Retired, Proposed |
| `jurisdiction` | MAC acronym |
| `mac_states` | Derived list of states served |
| `effective_date` / `retirement_date` | Coverage window |
| `revision_number` / `revision_date` |
| `specialty` | CMS-assigned clinical area |
| `benefit_category` |
| `diagnosis_codes` | List of ICD-10 codes with context (covered/not covered) |
| `procedure_codes` | CPT/HCPCS codes referenced |
| `indications` | Structured list of criteria bullet points (Docling output) |
| `limitations` | Non-covered situations |
| `documentation_requirements` | e.g., chart notes, lab results |
| `billing_modifiers` | Modifier guidance |
| `frequency_limits` | If specified |
| `article_refs` | Linked article IDs |
| `ncd_ref` | Linked NCD ID if applicable |
| `risk_signals` | Derived tags (e.g., “high denial risk”) |
| `source_url` / `retrieved_at` |
| `ingested_at` / `ingestion_version` |

#### 4.2 LCD Articles
| Field | Description |
| --- | --- |
| `article_id` |
| `lcd_id` |
| `article_type` | e.g., coding guidance, education |
| `jurisdiction` |
| `effective_date` |
| `coding_instructions` | chunked text |
| `documentation_tips` |
| `modifier_notes` |
| `diagnosis_mappings` | table mapping ICD→CPT combinations |
| `provider_action_items` |
| `fraud_indicators` | e.g., “overutilization warning” |

#### 4.3 NCD Policies & Decision Memos
Similar schema as LCD but national scope; include `national_effective_date`, `implementation_date`, `contractor_notes`, `benefit_category`, `evidence_summary`, `public_comment_summary`.

### 5. Clinical Detail Extraction
- **Docling templates** to capture structured sections:
  - `Indications` (positive coverage criteria) with subfields: `condition`, `test`, `documentation`.
  - `Contraindications/Limitations`: reason, clinical explanation.
  - `Coding guidelines`: mapping table (CPT-HCPCS ↔ ICD), bundling rules, modifiers.
  - `Documentation requirements`: enumerated list.
  - `Billing examples`: scenario text + codes.
- Each bullet anchored with paragraph ID/page number for traceability.

### 6. Alerts & Reporting
- After each ingestion run, notifier posts summary (new/updated/retired counts, MACs impacted, key NCD changes) to SIU + Claims Ops channels.
- Diff files stored in processed bucket: `lcd_new.json`, `lcd_retired.json`, `ncd_changes.json`.

### 7. Validation Gates
- **API integrity**: ensure API responses cover all jurisdictions; fallback to full download if pagination errors.
- **Schema validation**: Great Expectations on processed Parquet.
- **Crosslink checks**: every article must link to existing LCD ID; every LCD linked to valid jurisdiction.
- **Status transitions**: verify allowed transitions (e.g., Draft→Final). Unexpected transitions flagged.
- **Code range sanity**: ensure diagnosis/procedure codes match valid ICD-10/CPT dictionaries (already maintained in code reference dataset).

### 8. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Build LCD/LCD-article fetchers, raw staging, metadata tables |
| Week 2 | Normalize LCD schema, Docling pipeline for articles |
| Week 3 | NCD ingestion + decision memo processing |
| Week 4 | Glue catalog, KB sync, alerting & validation suites |
| Ongoing | Daily incremental sync, weekly NCD diff, monthly full re-ingest |

### 9. Open Questions
- Confirm retention duration for retired policies (default 7 years raw, 5 years processed?).
- Decide whether to expose coverage data via API or rely on Dynamo/Athena lookups only.
