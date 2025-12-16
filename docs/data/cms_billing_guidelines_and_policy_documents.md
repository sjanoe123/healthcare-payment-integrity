## CMS Billing Guidelines & Policy Documents — Ingestion Blueprint

### 1. Scope & Data Sources
| Source Category | Examples | Access Method | Notes |
| --- | --- | --- | --- |
| MLN Matters (Medicare Learning Network) | Weekly articles announcing billing/policy updates | CMS MLN RSS + HTML/PDF download | Contains billing instructions, modifier guidance, effective dates |
| Internet-Only Manuals (IOM) | Pub. 100-02 (Benefits), 100-04 (Claims Processing), etc. | CMS manual portal, PDF | Authoritative payment rules by chapter/section |
| Coverage Articles (LCD/NCD articles, FAQs) | LCD companion articles, coverage FAQs | CMS LCD Article search API (JSON) + PDF | Map MAC region + indication details |
| Fraud Prevention & Toolkit Documents | Fraud Prevention Toolkit, CPI alerts, fraud case studies | CMS / OIG static PDF pages | Often highlight suspect billing patterns |
| Policy Change Notifications | CMS transmittals, change requests | XML/HTML/PDF from CMS Portal | Provide crosswalk to manual sections |

### 2. Storage Topology & Cadence
- **Buckets** (per stage):
  - `s3://pi-${stage}-cms-policy-raw/<source>/<yyyy>/<mm>/....pdf`
  - `s3://pi-${stage}-cms-policy-processed/<source>/<yyyy>/<mm>/chunk_*.json`
- **Cadence**
  - *MLN/IOM/Transmittals/Fraud Toolkit*: EventBridge cron `cron(0 3 ? * MON-FRI *)` for daily diff check; monthly full hash verification.
  - *Coverage Articles*: Nightly incremental pull via LCD API to capture new articles or revisions.
  - *Manual re-ingestion*: quarterly (aligned with Implementation Unlock Plan §14) to rebuild processed chunks with latest Docling version.

### 3. Pipeline Strategy
1. **Crawler Lambda**
   - Triggered by EventBridge schedules per source cluster.
   - Fetch metadata feed (RSS/API/HTML), compare SHA256 hash vs DynamoDB tracking table (`cms_policy_hashes`).
   - Download new/updated documents → store binary in raw bucket with metadata object (JSON sidecar).
2. **Processing Lambda / Step Function**
   - S3 `raw/` uploads trigger Docling processing (PDF/HTML → JSON sections + plaintext).
   - Extract structured attributes: chapter, section, headings, paragraph text, tables, indications/contraindications, modifiers, billing examples.
   - Chunk text (approx. 1k tokens) with overlap, attach metadata (see section 4) → write to processed bucket.
3. **Glue Catalog & Athena**
   - Glue table `cms_policy_chunks` (schema: source, chapter, section, mac_region, effective_date, modifier_codes, indications, contraindications, billing_examples, chunk_text, chunk_id, ingestion_version, ingested_at, sha256, source_url).
   - Partitioned by `source` and `ingested_at` for efficient queries.
4. **Bedrock Knowledge Base Sync**
   - Daily Step Function batches processed chunks into Bedrock KB, including metadata tags.
   - Maintain `kb_sync_status` DynamoDB table for retry/backoff transparency.
5. **Observability**
   - CloudWatch metrics: `PolicyDownloads`, `DoclingFailures`, `ChunksCreated`, `KBRecordsUpserted`.
   - Alerts for download failures, processing errors > threshold, KB ingestion failures.
6. **Runbooks & Compliance**
   - Retain raw PDFs 7 years (Compliance Plan §5); processed JSON 3 years.
   - Access logging enabled on both buckets; sensitive indicators flagged (`restricted=false` for this dataset).

### 4. Metadata Schema (Expanded)
| Field | Description |
| --- | --- |
| `source` | MLN, IOM, Coverage, Fraud Toolkit, Transmittal |
| `document_id` | Unique identifier (e.g., MLN article number, manual chapter) |
| `chapter` / `section` / `subsection` | Manual hierarchy for precise references |
| `mac_region` / `jurisdiction` | Derived from coverage articles / manual applicability |
| `effective_date` / `implementation_date` / `expiration_date` | Distinguish when rule applies vs implemented |
| `policy_type` | Billing, coverage, fraud guidance, modifier policy |
| `cpt_hcpcs_range` | Extracted ranges (e.g., 99213-99215) |
| `icd_codes` / `condition_keywords` | From indications/contraindications text |
| `modifiers` | Applicable modifier list (e.g., 25, 59) |
| `billing_requirements` | Structured bullet list (documentation, frequency limits) |
| `indications` / `contraindications` | Parsed sections for clinical relevance |
| `supporting_docs_required` | e.g., “operative report”, “diagnostic imaging” |
| `risk_signals` | Fraud/abuse hints (e.g., “high-risk DME upcoding”) |
| `audience` | Provider, MAC, SIU, Payer |
| `source_url` / `retrieved_at` | Provenance |
| `ingested_at` / `ingestion_version` | Pipeline lineage |
| `checksum` | SHA256 of original doc for dedupe |

### 5. Implementation per Dataset
#### MLN Matters
- RSS feed → Lambda fetch; HTML to PDF conversion when necessary.
- Process with Docling; chunk by headings (Summary, Background, Implementation, Provider Action).
- Metadata emphasis: modifier instructions, CPT ranges, implementation dates.

#### Internet-Only Manuals (IOM)
- Quarterly full download of relevant manuals (Pub 100-02, 100-04, etc.).
- Use manual TOC to anchor chapter/section structure; chunk by section to preserve context for rules.
- Extract regulatory references, billing examples, and frequency limits.

#### Coverage Articles (LCD/NCD Articles)
- CMS LCD Article API: nightly incremental fetch.
- Link article to LCD ID + MAC; parse PDF attachments for indications, coding guidelines, documentation requirements.
- Tag with `jurisdiction`, `diagnosis_codes`, `procedure_codes`, and note if article supersedes prior versions.

#### Fraud Prevention & Toolkit Docs
- Monthly crawl of CMS/OIG fraud toolkit pages; store case studies, red-flag indicators.
- Metadata focuses on scheme type, affected specialties, recommended controls.

#### Policy Change Notifications / Transmittals
- Monitor CMS transmittal feed; map change requests to manual chapters + release numbers.
- Provide crosswalk metadata so agents can reconcile manual text updates with change requests.

### 6. Cadence & Roadmap
| Timeline | Activities |
| --- | --- |
| Week 1 | Finalize storage + metadata schemas; implement hash tracking table |
| Week 2 | Build MLN + Transmittal ingestion + Docling pipeline |
| Week 3 | Extend coverage article pipeline (API integration, metadata extraction) |
| Week 4 | Integrate IOM manuals, fraud toolkit, and KB sync automation |
| Ongoing | Daily incremental (MLN/articles), weekly diff checks, quarterly full manual reprocessing |

### 7. Open Questions / Next Checks
- Confirm if any manual sections contain restricted content requiring additional access controls.
- Determine whether we need to enrich chunk metadata with payer-specific rules beyond MAC (e.g., Medicare Advantage).
- Verify storage cost expectations for dual raw/processed buckets with retention policies.
