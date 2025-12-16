## Claims Data for Anomaly Detection & FWA — Ingestion Blueprint

### 1. Scope & Source Inventory
| Dataset Category | Examples | Format | Source |
| --- | --- | --- | --- |
| **Internal Claims Feeds** | Institutional/professional claims (837I/P), remittances (835), adjudicated claim extracts | EDI, Parquet, CSV | HPI data lake, payer SFTP feeds |
| **Historical FWA Cases** | SIU investigations, DOJ/OIG case summaries, Takedown press releases | JSON/PDF/HTML | SIU systems, OIG, DOJ |
| **Provider Billing Profiles** | Encounter summaries, utilization metrics per provider | CSV/Parquet | Payer warehousing feeds |
| **External Benchmarks** | CMS public use files (PUFs), Medicare Part B summary data, MEDPAR, Part D PDE | CSV | CMS data portal |
| **State All-Payer Claims Databases (APCD)** | Where available (e.g., Massachusetts, Colorado) | CSV/Parquet | State APCD portals (license) |
| **Anomaly Signals** | NCCI, MUE, prior auth denials, CARC/RARC codes, claim edits | Derived | Internal + CMS |

### 2. Storage Architecture & Cadence
- **Landing Zone**: `s3://pi-${stage}-claims-landing/<feed>/<yyyymmdd>/...` (raw EDI/CSV encrypted; PHI safe harbor per Compliance).
- **Curated Zone**: `s3://pi-${stage}-claims-curated/<dataset>/...` (parquetized, de-identified for analytics per HIPAA BAAs; PHI gating). Use Lake Formation access controls.
- **Analytics Zone**: Athena/Redshift Spectrum tables + Dynamo summary tables for high-speed lookups.
- **Cadence**
  - Internal claims feeds: daily batch (aligned with payer schedule); near-real-time optional via Kinesis if available.
  - CMS PUF/MEDPAR: annual release + quarterly refresh (Part B summary).
  - APCD: monthly/quarterly per state rules.
  - FWA case feeds: weekly ingest from SIU trackers + nightly scrape of OIG/DOJ updates.

### 3. Pipeline Strategy
1. **Ingestion**
   - Use AWS Transfer Family/SFTP ingestion for payer feeds; Kinesis Firehose for streaming sources.
   - EDI (837/835) ingested as-is; run X12 parser to convert into JSON segments (shared with EDI blueprint), then map to canonical claim schema.
   - External public datasets downloaded via AWS Data Exchange or manual script → raw S3.
2. **Normalization & De-ID**
   - Glue ETL to map claim fields to canonical schema (`claim_id`, `member_id`, `provider_id`, `service_line`, `diagnosis_codes`, `procedure_codes`, `units`, `billed_amount`, `allowed_amount`, `paid_amount`, `denial_codes`, `audit_flags`).
   - Apply tokenization/hashing per Compliance (member/provider IDs) when generating analytics outputs.
3. **Feature Engineering**
   - Build provider-level aggregates (utilization rates, upcoding ratios, modifier usage, time-of-day patterns).
   - Derive anomaly features: frequency vs peers, cost per unit, place-of-service anomalies, high-risk combinations (NCCI and PA violations), prior auth denial conversions.
   - Join with external benchmarks (CMS PUF, APCD) for percentile comparisons.
4. **Labeling & Case Linkage**
   - Link claims to SIU case labels (fraud, waste, abuse categories) for supervised models.
   - Store case metadata (scheme type, recovery amount) as training labels.
5. **Storage & Access**
   - Glue tables: `claims_canonical`, `claims_features_daily`, `provider_profiles`, `fwa_cases`, `external_benchmarks`.
   - Dynamo tables `provider_profile_latest`, `claim_edit_summary` for quick orchestrator lookups.
   - Bedrock KB: textual FWA case summaries, DOJ press releases (Docling processed) tagged with specialty, scheme type, CPT/ICD combos.

### 4. Metadata / Schema Highlights
#### Canonical Claim Record
| Field | Notes |
| --- | --- |
| `claim_id` |
| `claim_type` | professional/institutional/vision/pharmacy |
| `member_id` (tokenized) |
| `provider_id` (tokenized) |
| `npi` |
| `service_date_from` / `service_date_to` |
| `place_of_service` |
| `diagnosis_codes` (array) |
| `procedure_codes` |
| `revenue_codes` |
| `modifiers` |
| `units` |
| `billed_amount` / `allowed_amount` / `paid_amount` |
| `pricing_method` |
| `denial_codes` |
| `pa_reference` | link to PA record |
| `audit_flags` | e.g., NCCI hit, MUE hit |
| `ingested_at` / `source_feed` |

#### Provider Profile Features
| Field | Description |
| --- | --- |
| `provider_id` |
| `specialty` |
| `geography` |
| `avg_units_per_claim_by_code` |
| `avg_billed_amount_by_code` |
| `modifier_usage_rate` |
| `telehealth_ratio` |
| `weekend_claim_rate` |
| `peer_percentile_cost` |
| `fwa_case_association` |

#### FWA Case Record
| Field | Description |
| --- | --- |
| `case_id` |
| `source` | SIU, OIG, DOJ |
| `scheme_type` | upcoding, unbundling, kickback |
| `codes_involved` |
| `timeframe` |
| `outcome` | recovered amount, sanctions |
| `narrative_text` |

### 5. Validation & QA
- **Row counts**: compare ingested claim counts vs payer file manifest (±1% threshold).
- **Schema enforcement**: Great Expectations on canonical schema, ensuring required fields not null.
- **De-ID verification**: automated unit tests ensuring no raw PHI leaks into analytics tables.
- **Feature sanity checks**: ensure aggregates fall within realistic bounds (no negative totals, units within thresholds).
- **Benchmark alignment**: verify external dataset totals match published CMS numbers.

### 6. Observability
- Metrics: `ClaimFilesIngested`, `ClaimsRowsProcessed`, `ProviderProfilesUpdated`, `FWAEventsLinked`, `ValidationFailures`.
- Dashboards showing daily ingestion volume, anomaly features distribution, label coverage.
- Alerts on ingestion failures, schema violations, or sudden spikes/drop-offs in claim volume.

### 7. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Establish secure ingestion (Transfer/SFTP), raw/curated buckets, manifest tracking |
| Week 2 | Build canonical schema ETL + de-identification layer |
| Week 3 | Implement feature engineering + provider profiles, integrate external benchmarks |
| Week 4 | FWA case linkage, KB sync, observability, validation suites |
| Ongoing | Daily ingestion + monitoring, periodic benchmark updates |

### 8. Open Questions
- Confirm HIPAA mode requirements (PHI gating) for dev/stage environments; align with Compliance for tokenization approach.
- Determine which APCD datasets are licensed/accessible and any usage restrictions.
- Clarify retention policy for raw PHI claims (recommend per payer contract, typically 7–10 years) vs de-identified analytics (5 years).
