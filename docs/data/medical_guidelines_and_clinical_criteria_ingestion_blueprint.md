## Medical Guidelines & Clinical Criteria (NIH/AHRQ/USPSTF / etc.) — Ingestion Blueprint

### 1. Scope & Source Categories
| Dataset Category | Examples | Format | Source |
| --- | --- | --- | --- |
| Evidence-based guidelines | NIH (treatment guides), AHRQ ePSS, CDC clinical guidance, Healthy People 2030 resources | HTML/PDF/JSON | Agency sites, RSS feeds |
| Preventive recommendations | USPSTF graded statements | HTML/PDF | uspreventiveservicestaskforce.org |
| Low-value care avoidance | Choosing Wisely specialty lists | HTML/PDF | choosingwisely.org |
| Clinical decision trees | VA/DoD CPGs, NIH/AHRQ flowcharts, CDC algorithms | PDF/PNG | healthquality.va.gov, agency portals |
| Policy toolkits / clinical coverage bulletins | CMS Innovation Center toolkits, eviCore public criteria summaries, QualCare IPA MCG PDFs | PDF/HTML | CMS/OIG/eviCore/QualCare |
| Research & surveillance summaries | PubMed guideline filter, KFF briefs, OIG Work Plan narratives, Cochrane abstracts |
| International/global references | NICE guidance, WHO guidelines | HTML/PDF | nice.org.uk, who.int |

### 2. Storage & Cadence
- **Raw bucket**: `s3://pi-${stage}-guidelines-raw/<source>/<yyyy>/<mm>/...`
- **Processed bucket**: `s3://pi-${stage}-guidelines-processed/<source>/<yyyy>/<mm>/chunk_*.json`
- **Cadence:**
  - USPSTF: Weekly RSS poll + alert when grade changes.
  - Choosing Wisely: Monthly crawl of specialty lists.
  - VA/DoD CPGs: Quarterly check for new editions.
  - NIH/AHRQ/CDC/Healthy People: Monthly refresh via RSS/sitemaps; manual trigger for urgent updates.
  - eviCore public criteria & QualCare IPA PDFs: Monthly checks + manual import when payers publish new docs.
  - PubMed RSS watchers for select keywords (e.g., “overutilization”, “fraud detection”).
  - NICE/WHO/ECRI: Monthly ingestion; nightly diff check for NICE since updates frequent.

### 3. Pipeline Strategy
1. **Acquisition**
   - EventBridge schedule + Lambda per source cluster (NIH/AHRQ/CDC/HealthyPeople, USPSTF, Choosing Wisely, VA/DoD, eviCore/QualCare, NICE/WHO, ECRI/ACP/AHA/ADA, PubMed/Cochrane/KFF/OIG).
   - USPSTF: consume RSS + API, capture grade changes.
   - Choosing Wisely: scrape specialty pages, capture list version + society metadata.
   - VA/DoD: download PDF/ZIP bundles per condition.
   - eviCore/QualCare: download available PDFs, store with payer/source attribution.
   - NICE/WHO/ECRI/ACP/AHA/ADA: crawl sitemap or API; respect rate limits/licensing terms.
2. **Processing / Docling**
   - Convert PDFs/HTML to structured JSON (sections, headings, paragraphs, tables, decision trees).
   - Identify sections: Indications, Contraindications, Diagnostic Criteria, Treatment Recommendations, Evidence Strength, Billing/Documentation hints.
   - For decision trees, attempt to capture node/edge lists (Docling + custom parser) — fallback: store textual description + image reference.
3. **Metadata Enrichment**
   - Tag by `specialty`, `body_system`, `condition`, `evidence_grade` (USPSTF grades, VA/DoD strength of recommendation, NICE “strong/moderate”), `population`, `settings` (inpatient/outpatient), `source_type` (guideline, low-value list, payer criteria), `fraud_relevance`.
   - Map guidelines to code sets when codes explicitly referenced (CPT/HCPCS/ICD) using dictionary lookups.
   - Link to relevant codes if mentioned (CPT/HCPCS/ICD) via regex + dictionary matching.
4. **Glue / Dynamo**
   - Glue tables `clinical_guidelines` (chunks) and `clinical_sources` (metadata).
   - Dynamo table for rapid lookup by condition or guideline ID.
5. **Bedrock KB Integration**
   - Daily Step Function syncs processed chunks with metadata tags for agent retrieval.
6. **Alerts**
   - Weekly summary of new/updated guidelines; immediate alert for high-impact updates (USPSTF grade changes, NIH treatment revisions).

### 4. Metadata Schema (per chunk)
| Field | Description |
| --- | --- |
| `guideline_id` | Unique ID per source document |
| `source` | NIH, AHRQ, USPSTF, Choosing Wisely, VA/DoD, NICE, WHO, eviCore, QualCare, ACP, AHA, ADA, etc. |
| `title` |
| `section` / `subsection` |
| `condition` / `procedure` |
| `population` | e.g., adult, pediatric |
| `indications` | structured list if present |
| `contraindications` |
| `diagnostic_criteria` |
| `treatment_recommendations` |
| `documentation_requirements` |
| `evidence_grade` | USPSTF grade, VA/DoD strength, NICE recommendations, Choosing Wisely rationale |
| `fraud_risk_signal` | e.g., “high-risk DME misuse” |
| `code_refs` | list of referenced CPT/HCPCS/ICD codes |
| `supporting_references` | PubMed IDs, citations |
| `publication_date` / `retrieved_at` |
| `ingested_at` / `ingestion_version` |

### 5. Validation & QA
- Verify RSS/API responses parsed correctly (HTTP status, schema).
- Deduplicate by guideline ID + version.
- Ensure Docling extraction yields required sections; fallback to plain text if structured extraction fails (flag for manual review).
- Spot-check code references vs known dictionaries.

### 6. Observability
- Metrics: `GuidelineDownloads`, `DoclingFailures`, `GuidelineChunks`, `HighImpactUpdates`.
- Alerts when ingestion fails, when guideline flagged as high-impact (USPSTF grade change, NIH major update).

### 7. Implementation Timeline
| Timeline | Tasks |
| --- | --- |
| Week 1 | Build RSS/sitemap fetchers and raw staging |
| Week 2 | Docling pipeline for PDFs/HTML, metadata schema implementation |
| Week 3 | Tagging/enrichment (condition, specialty, codes), Glue/Dynamo setup |
| Week 4 | KB sync, alerts, validation dashboards |
| Ongoing | Monthly refresh + ad hoc manual triggers for urgent updates |

### 8. Open Questions
- Confirm access/licensing constraints for society-specific PDFs (e.g., MCG full set, payer portals) beyond what’s publicly available (QualCare subset, eviCore summaries).
- Determine priority list of PubMed/Cochrane keywords and whether to store entire abstracts or only key paragraphs.
- Decide if we need translation for non-English guidelines (NICE/WHO) and whether to limit to English-only for MVP.
