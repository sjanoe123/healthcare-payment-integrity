## EDI Files & Specifications (837/835/277/999/TA1/etc.) — Ingestion Blueprint

### 1. Scope & Source Inventory
| Artifact | Description | Format | Source |
| --- | --- | --- | --- |
| **X12 837I/837P/837D** | Institutional, Professional, Dental claim transactions | EDI (X12) | Trading partners, payer feeds |
| **X12 835** | Remittance Advice | EDI | Payers |
| **X12 277/277CA** | Claim status responses | EDI | Payers/Clearinghouses |
| **X12 999 / TA1** | Functional/Interchange acknowledgements | EDI | Clearinghouses |
| **X12 270/271** | Eligibility request/response | EDI | Providers/Payers (reference) |
| **X12 278** | Prior Authorization request/response | EDI | Providers/Payers |
| **X12 276/277** | Claim status inquiry/response | EDI | Payers |
| **X12 Implementation Guides** | TR3 documentation | PDF | X12.org (licensed) |
| **Companion Guides** | Payer-specific requirements | PDF | Payer portals |
| **HL7 FHIR IGs (Da Vinci PAS, Prior Auth Support)** | JSON/XML | HL7 (licensed) |

### 2. Storage & Cadence
- **Raw landing**: `s3://pi-${stage}-edi-raw/<transaction_set>/<yyyymmdd>/file.x12` (encrypted, PHI controls).
- **Parsed/processed**: `s3://pi-${stage}-edi-processed/<transaction_set>/<yyyymmdd>/...` (JSON or Parquet representing segments/elements).
- **Spec repository**: `s3://pi-${stage}-edi-specs/<transaction_set>/<version>/...` storing TR3 PDFs, companion guides, FHIR IG bundles.
- **Cadence**
  - Transaction feeds: near-real-time or batched daily per trading partner.
  - Companion guides: monitor quarterly for payer updates.
  - TR3 updates: align with X12 release cycles (biannual).
  - FHIR IG updates: monitor Da Vinci release announcements (quarterly).

### 3. Pipeline Strategy
1. **Ingestion**
   - For live EDI feeds: AWS Transfer Family (SFTP) or Kinesis ingestion; drop files into raw bucket with metadata manifest (trading partner, interchange control number, transaction set ID, received timestamp).
   - For specs (TR3, companion guides): manual upload or automated download (when allowed); track version in Dynamo.
2. **Parsing & Normalization**
   - Use X12 parser library (existing in repo?) to convert `.x12` into JSON structure (ISA/GS/ST segments, loops, elements).
   - Normalize to canonical schema per transaction (e.g., 837 claim lines referencing patient, provider loops; 835 adjustments referencing claim IDs).
   - For 835, split adjustments into line-level details with CARC/RARC mapping.
   - For 277/999, capture status codes, categories, and link back to originating transaction.
3. **Reference Library**
   - Store parsed TR3 metadata (segments, situational rules) in Dynamo/Glue table `x12_segment_specs` for validation.
   - Companion guide overrides stored as JSON, keyed by payer + transaction + version.
4. **Validation & Enrichment**
   - Validate incoming transactions against TR3 + companion rules (required segments, code sets, situational qualifiers).
   - Enrich parsed claims with crosswalks (e.g., map CARC codes to descriptions, link NPI to provider master, tie to prior auth references).
5. **Access & Analytics**
   - Glue tables: `edi_837_claims`, `edi_835_remits`, `edi_277_status`, `edi_999_ack`, `edi_companion_rules`.
   - Provide queryable views for debugging (ISA/GS metadata, file status, errors).
   - Provide API endpoints or Lambda to retrieve original EDI for re-transmission.

### 4. Metadata Schemas
#### 837 Claim Segment (simplified)
| Field | Description |
| --- | --- |
| `interchange_control_number` |
| `functional_group_id` |
| `transaction_set_control_number` |
| `claim_id` (CLM01) |
| `patient_control_number` |
| `bill_type` (837I) |
| `total_charges` |
| `service_lines` (array with procedure, modifiers, units, charges) |
| `diagnosis_codes` |
| `provider_npi` |
| `subscriber_id` |
| `place_of_service` |
| `received_timestamp` |

#### 835 Remittance Line
| Field | Description |
| --- | --- |
| `interchange_control_number` |
| `transaction_set_control_number` |
| `claim_id` |
| `service_line_number` |
| `paid_amount` |
| `allowed_amount` |
| `adjustment_group_code` |
| `adjustment_reason_code` (CARC) |
| `remark_codes` (RARC) |
| `payment_date` |
| `payer_name` |

#### 277 Status & 999 Ack
Include `original_transaction_control_number`, `status_category`, `status_code`, `status_description`, `error_segment`, `received_timestamp`.

#### Spec Metadata
| Field | Description |
| --- | --- |
| `transaction_set` |
| `version` |
| `payer` (if companion) |
| `segment_id` |
| `usage_indicator` (required/optional/situational) |
| `rule_text` |
| `effective_date` |

### 5. Validation & QA
- Automated validation pipeline comparing parsed transactions against TR3 spec (segment counts, required elements, qualifiers).
- Companion guide-specific tests (e.g., payer requires REF*G1 segment) with pass/fail reporting.
- Duplicate detection (interchange control numbers) and idempotent handling.
- Spot-check raw vs parsed output for each transaction type; unit tests using sample files.

### 6. Observability
- Metrics: `EDIInterchangesReceived`, `TransactionsParsed`, `ValidationErrors`, `CompanionViolations`, `AckFailures`.
- Dashboards per trading partner showing throughput, error rates, average file size.
- Alerts for validation spikes, missing acknowledgements, failed downloads.

### 7. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Set up raw landing (SFTP/Kinesis), manifest tracking, TR3/spec storage |
| Week 2 | Implement parser for 837 + 835, canonical schema, validation harness |
| Week 3 | Extend to 277/999/TA1, companion guide ingestion, Glue tables |
| Week 4 | Observability, diff reporting for specs, API/KB integration |
| Ongoing | Continuous ingestion, spec updates, trading partner onboarding |

### 8. Open Questions
- Confirm X12 licensing terms for storing TR3 PDFs and whether we can derive machine-readable schema from them.
- Identify existing X12 parser libs approved for use (or build custom) and ensure PHI handling compliance.
- Determine trading partner onboarding order and whether real-time ACK routing is required in MVP.
