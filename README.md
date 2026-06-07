# MedAstraX

Healthcare analytics XAI research prototype for evaluating visual explainability and grounded LLM augmentation in provider-facing dashboards.

**Dissertation:** *Human-Centered Explainable AI for Healthcare Analytics* — Syed Ali Kazmi, Auburn University

## Purpose

This repository implements the layered architecture described in the dissertation proposal. It supports three experimental dashboard conditions on the same underlying data and models:

1. **Baseline** — cohort analytics and risk scores without explicit explanations
2. **XAI-augmented** — SHAP-based local/global visual explanations
3. **LLM-augmented** — grounded text summaries and natural-language querying

The system is a **research instrument**, not a clinical deployment. It uses CMS synthetic Medicare claims-like data.

## Architecture

```
CMS Synthetic Data
       │
       ▼
┌──────────────────┐
│ Data Ingestion   │  download, parse, normalize, validate
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Feature Eng.     │  beneficiary & cohort features
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Modeling         │  logistic regression, XGBoost risk scores
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Explainability   │  SHAP local/global, stability indicators
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Grounded Language│  evidence-linked summaries, NL queries
└────────┬─────────┘
         ▼
┌──────────────────┐
│ UI + Instrument. │  React dashboard, event logging
└──────────────────┘
```

## Repository layout

| Path | Layer |
|------|-------|
| `backend/src/hc_analytics/ingestion/` | Data ingestion |
| `backend/src/hc_analytics/features/` | Feature engineering |
| `backend/src/hc_analytics/modeling/` | Predictive models |
| `backend/src/hc_analytics/explainability/` | XAI artifacts |
| `backend/src/hc_analytics/language/` | Grounded LLM layer |
| `backend/src/hc_analytics/instrumentation/` | Study telemetry |
| `backend/src/hc_analytics/api/` | FastAPI service |
| `frontend/` | React dashboard (3 conditions) |
| `data/` | Local data staging (not committed) |
| `artifacts/` | Models, explanations, logs (not committed) |
| `docs/` | Architecture and development notes |

## Prototype roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Repo scaffold, versioning, config | Done |
| 1 | CMS synthetic data ingestion | Done |
| 2 | Feature store + cohort summaries | Done |
| 3 | Risk models (hospitalization, high-utilization, elevated cost) | Done |
| 4 | SHAP explainability + caching | Done |
| 5 | Baseline dashboard | Done |
| 6 | XAI-augmented dashboard | Done |
| 7 | Grounded language layer + LLM dashboard | Planned |
| 8 | Instrumentation + study export | Planned |

## Quick start

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn hc_analytics.api.app:app --reload

# Frontend (after Phase 5)
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env` and configure paths before running pipelines.

```bash
# Data pipelines (after raw CMS files are staged)
python -m hc_analytics.ingestion
python -m hc_analytics.features
python -m hc_analytics.modeling
python -m hc_analytics.explainability
# Faster local iteration (skips full beneficiary-year cache):
python -m hc_analytics.explainability --max-rows 1000
```

On macOS, install OpenMP (`brew install libomp`) if you want XGBoost training in addition to logistic regression.

## Data

Download CMS DE-SynPUF (or equivalent synthetic Medicare) files into `data/raw/`. See `docs/DATA.md` for expected file layout and provenance tracking.

## License

Research use. Not for clinical deployment.
