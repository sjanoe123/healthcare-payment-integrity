## Provider Data, Credentialing, and Exclusion Lists — Ingestion Blueprint

### 1. Scope & Source Inventory
| Dataset Category | Examples | Format | Source |
| --- | --- | --- | --- |
| **NPPES NPI Registry** | Full monthly file (NPPES Downloadable File) | CSV | https://download.cms.gov/nppes/NPI_Files.html |
| **PECOS Enrollment** | Provider enrollment records | CSV | CMS PECOS data (requires access) |
| **CMS Opt-Out & Preclusion Lists** | Provider opt-out affidavits, preclusion list | CSV/PDF | CMS |
| **OIG LEIE (List of Excluded Individuals/Entities)** | Exclusion list | CSV | https://oig.hhs.gov/exclusions/exclusions_list.asp |
| **SAM.gov Exclusions (EPLS)** | Federal debarments | CSV | SAM.gov |
| **State Medicaid Exclusion Lists** | State-level exclusions | PDF/CSV | State Medicaid sites |
| **Medicare Ordering/Referring Report** | Eligible providers | CSV | CMS |
| **Provider Credentialing Data** | CAQH ProView extracts, payer credentialing exports | CSV/JSON | CAQH/payer systems |
| **Provider Network Directories** | Provider rosters by plan | CSV/XLS | Payer portals |
| **Board Certifications** | ABMS / specialty board lists | CSV/XML | Board APIs (license) |
| **Licensure Data** | State medical boards | CSV/JSON | FSMB/state boards |

### 2. Storage & Cadence
- **Raw bucket**: `s3://pi-${stage}-provider-raw/<dataset>/<yyyymmdd>/...`
- **Processed bucket**: `s3://pi-${stage}-provider-processed/<dataset>/<yyyymmdd>/...` (Parquet + Docling chunks for PDF lists).
- **Cadence**
  - NPPES: weekly delta (CMS publishes weekly incremental + monthly full).
  - PECOS / Medicare ordering-referring: monthly.
  - OIG LEIE: monthly with mid-month supplements.
  - SAM.gov: weekly.
  - State Medicaid exclusions: monthly (varies by state) + manual triggers.
  - Credentialing exports/network directories: monthly or on-demand from payer feeds.
  - Board/licensure updates: quarterly.

### 3. Pipeline Strategy
1. **Acquisition**
   - Automated download scripts per dataset (CMS, OIG, SAM, states) via HTTPS/SFTP; handle credentials via Secrets Manager.
   - For CAQH/credentialing data requiring manual export, provide upload UI or AWS S3 drop folder.
2. **Processing & Normalization**
   - **NPPES/PECOS**: Glue ETL to standardize provider entity info (NPI, taxonomy, addresses, status, identifiers).
   - **Exclusion Lists** (LEIE, SAM, state): parse CSV/PDF via Docling (for PDF), map to common schema with exclusion reason, effective dates, reinstatement status.
   - **Credentialing/Network**: normalize to schema capturing plan participation, contract effective dates, specialties, accepting new patients, telehealth availability.
   - **Licensure/Board**: ingest license numbers, status, expiry, disciplinary actions.
3. **Entity Resolution**
   - Use deterministic + probabilistic matching (NPI, name, DOB, license) to link records across sources.
   - Maintain `provider_master` table with best-known attributes and data lineage.
4. **Storage & Serving**
   - Glue tables: `provider_master`, `provider_exclusions`, `provider_credentials`, `provider_networks`.
   - Dynamo table `provider_snapshot_latest` keyed by `npi` for low-latency lookups; includes exclusion flags and enrollment status.
   - Bedrock KB: textual exclusion notices, sanction descriptions, state bulletin narratives.
5. **Alerting & Reporting**
   - After each ingestion, produce diff summary: newly excluded providers, reinstatements, credentialing changes.
   - Alerts to SIU/Provider Relations when high-risk provider appears in exclusion list or loses licensure.

### 4. Metadata Schemas
#### Provider Master Record
| Field | Description |
| --- | --- |
| `npi` |
| `entity_type` | Individual/Organization |
| `name_primary` / `name_secondary` |
| `taxonomy_codes` |
| `primary_specialty` |
| `practice_addresses` (list) |
| `mailing_address` |
| `phone` |
| `email` (if available) |
| `enrollment_status` | Active, Pending, Revoked |
| `pecos_status` |
| `opt_out_flag` |
| `board_certifications` |
| `license_numbers` (state, status, expiration) |
| `network_participation` | list of plan IDs |
| `telehealth_flag` |
| `last_verified_at` |

#### Exclusion Record
| Field | Description |
| --- | --- |
| `npi` / `provider_name` |
| `source` | OIG, SAM, State, CMS Preclusion |
| `exclusion_reason` |
| `effective_date` |
| `reinstatement_date` |
| `case_number` |
| `notes` |

#### Credentialing/Network Record
| Field | Description |
| --- | --- |
| `npi` |
| `plan_id` |
| `effective_date` |
| `termination_date` |
| `contract_type` |
| `tier` |
| `accepting_new_patients` |
| `credential_status` |

### 5. Validation & QA
- Row-count checks vs published totals (e.g., NPPES weekly file counts).
- Schema validation per dataset.
- Entity resolution QA: sample cross-source merges to ensure accuracy.
- Ensure exclusion updates propagate to provider master (flag consistency tests).
- Audit logs verifying PHI/PII access controls (PII only; PHI not expected).

### 6. Observability
- Metrics: `ProviderFilesDownloaded`, `ProvidersProcessed`, `ExclusionsAdded`, `CredentialsUpdated`, `ValidationFailures`.
- Dashboards showing newly excluded providers by specialty/state, credentialing backlog, lookup latency.
- Alerts for download failures, large swings in provider counts, mismatched entity resolution.

### 7. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Automate NPPES/LEIE/SAM downloads, raw storage, initial Glue crawlers |
| Week 2 | Build normalization ETL + entity resolution pipeline |
| Week 3 | Integrate credentialing/network datasets, Dynamo serving layer |
| Week 4 | Alerting/diff reporting, Bedrock KB sync, observability |
| Ongoing | Weekly/monthly ingests per dataset cadence, manual overrides as needed |

### 8. Open Questions
- Confirm access to PECOS, CAQH, and board-certification feeds (licensing/licensure requirements).
- Determine state Medicaid exclusion list priority order and any legal restrictions on redistribution.
- Decide retention period for provider credentialing files (recommend ≥7 years for audit).
