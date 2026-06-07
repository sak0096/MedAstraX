# Data guide

## Source

Primary planned source: **CMS DE-SynPUF** (synthetic Medicare enrollment, fee-for-service claims, prescription drug events).

Synthetic data is appropriate for research prototyping and user studies. It must not be used for clinical deployment or population inference.

## Local layout

```
data/
├── raw/           # Downloaded CMS files (gitignored)
│   ├── beneficiary/
│   ├── inpatient/
│   ├── outpatient/
│   ├── carrier/
│   └── prescription/
└── processed/     # Cleaned parquet tables (gitignored)
    ├── beneficiaries.parquet
    ├── claims.parquet
    ├── prescription_events.parquet
    └── feature_store.parquet
```

## Provenance

Each ingestion run should record in `artifacts/ingestion_manifest.json`:

- source dataset name and URL
- download/extraction timestamp
- file checksums
- schema version
- transformation script version (git commit)

## Getting started (Phase 1)

1. Download DE-SynPUF sample files from [CMS](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files/cms-2008-2010-data-entrepreneurs-synthetic-public-use-file-de-synpuf).
2. Place files under `data/raw/` following the layout above.
3. Run `python -m hc_analytics.ingestion.pipeline` (to be implemented in Phase 1).
