# Data guide

## Source

**CMS Synthetic Medicare Enrollment, FFS Claims, and PDE** (Synthetic RIF format).

- Collection: [data.cms.gov](https://data.cms.gov/collection/synthetic-medicare-enrollment-fee-for-service-claims-and-prescription-drug-event)
- User guide: `docs/cms-synthetic-rif-user-guide.pdf`
- ~8,671 synthetic beneficiaries, 2015–2025 enrollment snapshots, 2015–2023 claims window

Synthetic data is appropriate for research prototyping and user studies. It must not be used for clinical deployment or population inference.

## Local layout

```
data/
├── raw/                         # Downloaded CMS files (gitignored)
│   ├── beneficiary/             # beneficiary_2015.csv … beneficiary_2025.csv
│   ├── inpatient/inpatient.csv
│   ├── outpatient/outpatient.csv
│   ├── carrier/carrier.csv
│   ├── snf/snf.csv
│   ├── dme/dme.csv
│   ├── hha/hha.csv
│   ├── hospice/hospice.csv
│   └── prescription/pde.csv
└── processed/                   # Cleaned parquet tables (gitignored)
    ├── beneficiaries.parquet
    ├── claims.parquet
    └── prescription_events.parquet
```

## Ingestion

From the repo root (after `./scripts/setup.sh`):

```bash
source backend/.venv/bin/activate
python -m hc_analytics.ingestion
```

Outputs:

| Table | Contents |
|-------|----------|
| `beneficiaries.parquet` | Panel of beneficiary-year enrollment rows |
| `claims.parquet` | Unified FFS claims across inpatient, outpatient, carrier, SNF, DME, HHA, hospice |
| `prescription_events.parquet` | Part D (PDE) events |

Provenance is written to `artifacts/ingestion_manifest.json` (checksums, row counts, git commit).

## Feature engineering (Phase 2)

```bash
python -m hc_analytics.features
```

Outputs:

| Table / artifact | Contents |
|------------------|----------|
| `feature_store.parquet` | Beneficiary-year utilization, cost, Rx burden, chronic flags, readmission proxy, next-year labels |
| `artifacts/cohort_summary.json` | Dashboard-ready cohort aggregates by state and age group |
| `artifacts/feature_manifest.json` | Feature run provenance |

## Format notes

- Raw files are **pipe-delimited** (`|`), not comma-separated.
- Join key across all tables: `bene_id` / `BENE_ID`.
- Preserve leading zeros when inspecting raw files outside the ingestion pipeline.
