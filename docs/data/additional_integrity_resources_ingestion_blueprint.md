## Additional Integrity Resources (OIG Work Plan, Dartmouth Atlas, Plan Catalogs, etc.) — Ingestion Blueprint

### 1. Scope & Source Inventory
| Dataset Category | Examples | Format | Source |
| --- | --- | --- | --- |
| **OIG Work Plan** | Monthly updates on audit priorities | HTML/PDF/CSV | https://oig.hhs.gov/reports-and-publications/workplan/ |
| **OIG/DOJ Enforcement Releases** | Press releases, settlement summaries | HTML/PDF | OIG, DOJ |
| **CMS Program Integrity Transmittals** | CMS Fraud Prevention instructions | PDF | CMS |
| **Dartmouth Atlas** | Health care variation statistics | CSV | https://www.dartmouthatlas.org/ (download center) |
| **State Medicaid Integrity Plans** | Program integrity strategies | PDF | State Medicaid sites |
| **Payer Plan Catalogs** | Benefit booklets, SBCs, plan comparisons | PDF/XLS | Payer portals |
| **Public Rate/Policy Notices** | State DOI rate filings, plan policy updates | PDF | SERFF public access (where allowed) |
| **Industry Reports / Whitepapers** | KFF, AHIP, NAIC fraud reports | PDF/HTML |

### 2. Storage & Cadence
- **Raw bucket**: `s3://pi-${stage}-integrity-raw/<source>/<yyyy>/<mm>/...`
- **Processed bucket**: `s3://pi-${stage}-integrity-processed/<source>/<yyyy>/<mm>/chunk_*.json`
- **Cadence**
  - OIG Work Plan: monthly crawl (new items flagged by date).
  - DOJ/OIG enforcement: weekly scrape.
  - CMS integrity transmittals: weekly check.
  - Dartmouth Atlas: annual release + ad hoc updates.
  - Plan catalogs/SBCs: align with open enrollment (annual) + midyear updates.
  - State Medicaid integrity plans: annual/biannual.

### 3. Pipeline Strategy
1. **Acquisition**
   - EventBridge + Lambda per source cluster (OIG/DOJ, CMS, Dartmouth, state Medicaid, payer catalogs).
   - Use site RSS or HTML scraping; store metadata (title, publish date, source URL).
2. **Processing**
   - Docling transform for PDFs/HTML to extract sections (audits, risk areas, geographic focus, dollars at risk).
   - For Dartmouth Atlas, ingest CSV datasets into Parquet; maintain dictionary of geographies (hospital referral regions, counties).
   - Plan catalogs/SBCs: parse benefit tables (copays, coinsurance, limits) for cross-reference with PA/eligibility module.
3. **Metadata Enrichment**
   - Tag documents by topic (e.g., DME fraud, telehealth, cardiology), geography (state, HRR), population (Medicare/Medicaid/commercial), risk level.
   - Link OIG Work Plan items to affected code sets (via regex + dictionary) and coverage policies.
4. **Serving & KB Integration**
   - Glue tables: `oig_work_plan`, `oig_doj_enforcement`, `dartmouth_variation`, `plan_catalogs`.
   - Bedrock KB sync for textual narratives (Work Plan descriptions, plan catalog benefit explanations) for RAG.
5. **Diff & Alerting**
   - For each ingest, compile summary of new OIG Work Plan items, settlements, plan catalog changes, Dartmouth metric updates.
   - Post to Compliance/SIU Slack for awareness.

### 4. Metadata Schemas
#### OIG Work Plan Item
| Field | Description |
| --- | --- |
| `workplan_id` |
| `title` |
| `description` |
| `focus_area` | e.g., DME, Medicare Part B |
| `program` | Medicare, Medicaid |
| `expected_release` |
| `status` | Active, Completed |
| `geography` |
| `codes_impacted` |
| `risk_level` |
| `source_url` |

#### Dartmouth Atlas Metric
| Field | Description |
| --- | --- |
| `metric_id` |
| `metric_name` |
| `geography` | HRR, county |
| `year` |
| `value` |
| `national_percentile` |
| `topic` |

#### Plan Catalog Entry
| Field | Description |
| --- | --- |
| `payer_id` |
| `plan_id` |
| `plan_name` |
| `coverage_year` |
| `network_type` |
| `benefit_category` |
| `copay` / `coinsurance` |
| `deductible` |
| `oop_max` |
| `notes` |

### 5. Validation & QA
- Schema validation per dataset.
- Ensure no duplicate Work Plan items (match by ID + title).
- Verify Dartmouth metrics match published counts.
- Spot-check Docling extraction vs original PDF for plan catalog tables.

### 6. Observability
- Metrics: `IntegrityDocsDownloaded`, `WorkPlanItemsProcessed`, `PlanCatalogsProcessed`, `ValidationFailures`.
- Dashboards showing new OIG items per month, plan catalog change volume, Dartmouth metrics refresh.
- Alerts on download failures or parsing errors.

### 7. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Build crawlers for OIG/DOJ Work Plan + enforcement releases, raw storage |
| Week 2 | Process Dartmouth Atlas CSVs, set up Glue tables |
| Week 3 | Parse plan catalogs/SBCs, integrate with PA/eligibility metadata |
| Week 4 | Alerts, dashboards, KB sync |
| Ongoing | Monthly/annual ingests per dataset |

### 8. Open Questions
- Confirm which payer plan catalogs are priority and whether authentication is required.
- Determine whether SERFF filings (state DOI) can be scraped programmatically or require manual download.
- Verify Dartmouth Atlas usage rights and citation requirements for derived analytics.
