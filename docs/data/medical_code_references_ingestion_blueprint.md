## Medical Code References (CPT/HCPCS/ICD/DRG/Revenue/POS) — Ingestion Blueprint

### 1. Scope & Sources
| Dataset | Description | Format | Source |
| --- | --- | --- | --- |
| CPT (AMA) / **Placeholder via CMS RVU files** | Procedural code set (official AMA data requires license). Interim placeholder uses CMS PFS relative value files (e.g., RVU25A) to derive CPT/HCPCS codes, short descriptors, RVUs, modifiers | AMA XML/CSV (future) / CMS fixed-width TXT (current placeholder) | AMA CPT distribution (future) / CMS PFS Relative Value Files (https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files) |
| HCPCS Level II | Supply/drug codes | CSV | CMS quarterly HCPCS file |
| ICD-10-CM/PCS | Diagnosis/procedure codes | XML/TXT | CMS ICD updates |
| ICD-10-PCS | Inpatient procedures | same | CMS |
| DRG (MS-DRG/Grouper) | Diagnosis Related Groups definitions | CSV/TXT | CMS DRG downloads |
| Revenue Codes | UB-04 revenue codes | CSV | NUBC references (public subset) |
| Place of Service (POS) | POS code set | CSV | CMS POS table |
| Modifiers | CPT/HCPCS modifiers | CSV | Derived from AMA + CMS |
| Crosswalks | ICD↔DRG, CPT↔ICD, CPT↔Revenue | Various | CMS, internal mapping |

### 2. Storage & Cadence
- **Raw bucket**: `s3://pi-${stage}-codes-raw/<dataset>/<release>/...`
- **Processed bucket**: `s3://pi-${stage}-codes-processed/<dataset>/<release>/parquet/`
- **Cadence:**
  - CPT: **placeholder** = CMS RVU release (annual + quarterly corrections). Once AMA license secured, swap to official distribution using same pipeline entry point.
  - HCPCS: quarterly.
  - ICD: annual (Oct) with addenda.
  - DRG: annual (FY) + corrections.
  - POS/Revenue: annual + ad hoc.
  - EventBridge schedule `cron(0 5 1 1,4,7,10 ? *)` to check updates; manual upload support for CPT licensing.

### 3. Pipeline Strategy
1. **Acquisition**
   - CPT (placeholder): automated download of CMS RVU ZIP (e.g., `RVU25A.ZIP`) → raw bucket `codes-raw/cpt_rvu/<release>/`. Release detector monitors CMS page hashes.
   - CPT (future AMA): secured upload/manual ingest; pipeline compatible with both sources.
   - HCPCS/ICD/DRG/POS: Lambda download from CMS; store manifest with `release_id`, `sha256`, `license_notes`.
2. **Normalization**
   - **CPT placeholder flow**: parse `PPRVUxxA.TXT` fixed-width file to extract `code`, `modifier`, `short_desc`, RVU fields, status/global period indicators. Tag records with `data_source = "CMS_RVU_placeholder"` for traceability.
   - Once AMA feed available, same schema extended with long descriptions + proprietary fields.
   - Standardize field names (`code`, `short_desc`, `long_desc`, `effective_date`, `termination_date`, `status`, `parent_code`, etc.).
   - For crosswalks, ensure many-to-many mapping tables with versioning.
3. **Metadata Enrichment**
   - Add semantic tags (specialty, body system, service category) from internal dictionaries.
   - Link ICD codes to DRG groupers, CPT to revenue codes, modifiers to base codes.
4. **Catalog & Access**
   - Glue tables per dataset; Athena views for unified search (e.g., `SELECT * FROM codes_unified WHERE code='99213'`).
   - DynamoDB `codes_latest` table for low-latency lookups (key `code`, attributes: dataset, descriptions, status, effective dates).
5. **RAG Integration**
   - Code descriptions chunked (short + long desc, clinical notes) for Bedrock KB with metadata (code type, body system, synonyms, example usage).
6. **Diff & Alerts**
   - Generate `codes_additions`, `codes_deletions`, `codes_changes` per release.
   - Notify Claims Ops + SIU when major updates arrive (e.g., new ICD sets, CPT revisions).

### 4. Metadata Schemas
#### CPT / HCPCS
| Field | Description |
| --- | --- |
| `code` |
| `short_desc` / `long_desc` |
| `effective_date` / `termination_date` |
| `status_code` | (A=Active, D=Deleted, etc.) |
| `specialty_category` | Derived from AMA taxonomy |
| `global_period` (if available) |
| `modifier_applicability` |
| `revenue_code_suggestions` |
| `icd_mappings` | optional list |
| `betos_code` |
| `coverage_flag` | Medicare coverage indicator |

#### ICD-10 (CM/PCS)
| Field | Description |
| --- | --- |
| `code` |
| `description` |
| `chapter` / `block` |
| `category` |
| `effective_date` |
| `laterality` (if applicable) |
| `sex_code` |
| `newborn_code_flag` |
| `excludes1` / `excludes2` lists |
| `includes_notes` |

#### DRG
| Field | Description |
| --- | --- |
| `drg_code` |
| `title` |
| `weight` |
| `geometric_mean_los` |
| `arithmetic_mean_los` |
| `cc_mcc` indicator |
| `icd_principal_requirements` |
| `icd_secondary_requirements` |
| `procedure_requirements` |

#### Revenue/POS/Modifiers
Include `code`, `description`, `status`, `effective_date`, `category`, `notes`.

### 5. Validation & QA
- Schema checks per dataset (types, required columns, allowed values).
- Cross-dataset consistency: ensure references exist (e.g., POS codes used in MPFS site-of-service fields).
- CPT licensing compliance: restrict access to raw/processed CPT data per contract.
- Diff reports for each release, including code counts vs prior release.

### 6. Observability
- Metrics: `CodeReleaseDetected`, `FilesDownloaded`, `RowsProcessed`, `DiffAlerts`.
- Alerts on download/validation failures, CPT upload missing, crosswalk mismatches.

### 7. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Build release detector + raw staging for HCPCS/ICD |
| Week 2 | Normalize HCPCS + ICD, create Glue tables |
| Week 3 | Integrate DRG, POS, Revenue; diff reporting |
| Week 4 | CPT ingestion workflow (manual upload + processing), Dynamo / KB sync |
| Ongoing | Quarterly release ingestion + alerts |

### 8. Open Items
- Confirm licensing arrangements + access controls for CPT distribution.
- Determine if crosswalks should include payer-specific mappings beyond CMS references.
- Decide whether to surface API endpoints for code search.
