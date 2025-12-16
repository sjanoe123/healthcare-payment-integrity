## CMS Fee Schedules, RVUs, and Pricing Files — Ingestion Blueprint

### 1. Scope & Data Sources
| Dataset | Description | Format | Source |
| --- | --- | --- | --- |
| **MPFS (Physician Fee Schedule)** | National + locality-specific payment rates, RVUs, modifiers | CSV/TXT + Addenda (A–E) | CMS PFS downloads (https://www.cms.gov/medicare/payment/physicianfeesched/pfs-relative-value-files) |
| **RVU Components** | Work RVU, PE RVU, malpractice RVU for each CPT | CSV | Same release |
| **HCPCS Quarterly Update** | Code status, pricing indicators | CSV | CMS HCPCS quarterly file |
| **Ambulance Fee Schedule** | Base rates + mileage | CSV | CMS ambulance downloads |
| **Clinical Lab Fee Schedule (CLFS)** | Lab test pricing by locality | CSV | CMS CLFS portal |
| **DMEPOS Fee Schedule** | Durable medical equipment pricing | CSV | CMS DMEPOS downloads |
| **Anesthesia CF / GPCI** | Conversion factors, geographic adjustments | CSV | CMS PFS files |
| **Outpatient/ASC Addenda** | OPPS & ASC payment indicators | CSV | CMS OPPS/ASC site |
| **Historical archives** | Prior year releases for comparison | same | required |

### 2. Storage Layout & Cadence
- **Raw bucket**: `s3://pi-${stage}-fee-raw/<year>/<dataset>/file.zip`
- **Processed bucket**: `s3://pi-${stage}-fee-processed/<year>/<dataset>/parquet/`
- **Cadence**
  - MPFS/RVU/GPCI/HCPCS: Annual major release (Nov) + quarterly corrections; check monthly for errata.
  - Ambulance, CLFS, DMEPOS: Annual + ad hoc mid-year adjustments.
  - OPPS/ASC: Quarterly.
  - EventBridge schedule `cron(0 4 1 * ? *)` for monthly release check + manual on-demand trigger.

### 3. Pipeline Strategy
1. **Release Detection**
   - Lambda scrapes CMS download page metadata (file names include year+quarter) and compares against Dynamo table `fee_release_meta` (hash + last_downloaded).
   - New release triggers Step Function `FeeScheduleIngestion` with dataset list.
2. **Download & Raw Staging**
   - Each dataset handled by dedicated Lambda to stream ZIP → raw bucket; write manifest containing `dataset_name`, `release_id`, `source_url`, `sha256`.
3. **Normalization**
   - **MPFS Parser**
     - Convert multiple addenda into unified Parquet with columns: `hcpcs`, `modifier`, `status_code`, `facility_nonfacility`, `rvu_work`, `rvu_pe`, `rvu_mp`, `nonfacility_payment`, `facility_payment`, `locality`, `conversion_factor`, `global_period`, `multiple_surgery_flag`, `bilateral_flag`, etc.
     - Join with GPCI + conversion factor tables.
   - **HCPCS Update Parser**
     - Track code lifecycle (new/deleted/status change) and map to pricing indicators, BETOS, TOS.
   - **Ambulance/CLFS/DMEPOS**
     - Normalize locality-specific rates, inflation adjustments, supplier class.
   - **OPPS/ASC**
     - Capture APC, SI, packaging flags, payment rates.
4. **Analytics Layer**
   - Glue tables: `mpfs_rates`, `mpfs_rvu_components`, `hcpcs_quarterly`, `ambulance_rates`, `clfs_rates`, `dmepos_rates`, `opps_rates`.
   - Materialized Athena views for quick queries (e.g., `SELECT * FROM mpfs_rates WHERE hcpcs='99213' AND year=2025`).
   - Redshift Spectrum external schema for heavier analytics (optional per Planning doc §4).
5. **Metadata Enrichment**
   - Enrich each record with `release_id` (year+Q), `jurisdiction/locality`, `specialty` (if available), `cost_center_tag` (per Business Case), and derived risk metrics (e.g., top 10% increase vs prior release).
6. **Bedrock KB Integration**
   - Payment explanation snippets (from Addendum A/B text) chunked and synced to KB with metadata (code, locality, payment change reason) for agents to reference.
7. **Diff Reporting & Alerts**
   - For each release produce diff vs prior release: rate delta, RVU delta, status changes.
   - Alert (Slack/email) summarizing big movements (>10%), new/deleted codes, locality-specific anomalies.

### 4. Metadata Schemas
#### MPFS / RVU Records
| Field | Description |
| --- | --- |
| `release_id` | e.g., 2025Q1 |
| `hcpcs_code` |
| `hcpcs_modifiers` | comma-separated |
| `status_code` | Indicator (e.g., A, B, T) |
| `global_period` |
| `multiple_procedure_flag` |
| `bilateral_indicator` |
| `site_of_service` | facility/nonfacility |
| `locality` | numeric or “nationwide” |
| `conversion_factor` |
| `rvu_work` / `rvu_pe` / `rvu_mp` |
| `total_rvu` |
| `payment_rate_facility` |
| `payment_rate_nonfacility` |
| `geographic_adjusted_rate` |
| `effective_date` / `termination_date` |
| `change_type` | new, revised, deleted |
| `prior_release_rate` / `delta_rate` |
| `documentation_notes` | from addenda text |

#### HCPCS Quarterly Update
| Field | Description |
| --- | --- |
| `hcpcs_code` |
| `short_desc` / `long_desc` |
| `status_action` | Add, Delete, Change |
| `pricing_indicator` |
| `coverage_indicator` |
| `effective_date` |
| `betos_code` |

#### Ambulance / CLFS / DMEPOS / OPPS
Include rate, locality, APC, SI, packaging flag, mileage components, supplier class, etc., aligning with CMS file layouts.

### 5. Validation & QA
- Schema validation via Great Expectations (type checks, required fields, allowed sets).
- Cross-verify MPFS totals against CMS published summary (e.g., row counts, number of unique HCPCS).
- Delta checks vs prior release with thresholds (flag >15% change for non-inflation adjustments).
- Spot-check sample codes across analytics views and Dynamo lookups.
- Unit tests covering parsing, conversion factor joins, diff generator.

### 6. Observability
- Metrics: `FeeReleaseDetected`, `FilesDownloaded`, `RowsProcessed`, `DiffAlerts`, `ValidationFailures`.
- CloudWatch dashboards showing rate deltas by category, ingestion duration, error counts.
- Alerts when downloads fail, validation fails, or diff generator detects large swings.

### 7. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Release detector, raw staging for MPFS/RVU/HCPCS |
| Week 2 | MPFS normalization + validation + diff engine |
| Week 3 | Extend to Ambulance/CLFS/DMEPOS, integrate diff reporting |
| Week 4 | OPPS/ASC ingestion, Glue/Athena tables, KB sync, observability wiring |
| Ongoing | Monthly release check + quarterly ingest, delta alerts |

### 8. Open Questions
- Decide whether to push diff summaries to downstream dashboards (Grafana/QuickSight) for Finance stakeholders.
- Confirm retention policy (raw 10 years, processed 5 years recommended).
- Determine if we need to expose API endpoints for real-time fee lookup or rely on Athena/Dynamo.
