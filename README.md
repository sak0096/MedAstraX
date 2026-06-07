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

## Prerequisites

- Python 3.9+
- Node.js 18+ and npm (for the dashboard)
- CMS synthetic files staged under `data/raw/` (see [docs/DATA.md](docs/DATA.md))
- macOS only: `brew install libomp` if you want XGBoost training alongside logistic regression

## Quick start

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — set HC_EXPERIMENTAL_CONDITION for your study arm (see below)
```

### 2. Install backend and run pipelines

Run from `backend/` with the virtualenv activated.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# After raw CMS files are in data/raw/
python -m hc_analytics.ingestion
python -m hc_analytics.features
python -m hc_analytics.modeling
python -m hc_analytics.explainability
# Faster dev iteration (partial SHAP cache):
# python -m hc_analytics.explainability --max-rows 1000
```

Processed outputs land in `data/processed/`. Models, explanations, and logs are written under `artifacts/` (gitignored).

### 3. Start API and dashboard

```bash
# Terminal 1 — API (from repo root or backend venv)
cd backend && source .venv/bin/activate
uvicorn hc_analytics.api.app:app --reload
# or: ../scripts/dev.sh

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` and `/health` to the FastAPI service.

Check readiness: `GET http://127.0.0.1:8000/api/meta` (reports data, models, predictions, explanations, and instrumentation flags).

## Study conditions

Set `HC_EXPERIMENTAL_CONDITION` in `.env` before starting the API. Restart the backend after changing condition.

| Condition | `.env` value | Dashboard affordances |
|-----------|--------------|------------------------|
| Control | `baseline` | Cohort charts, sortable risk table, beneficiary drill-down, CSV/PDF export |
| XAI | `xai` | Baseline + global SHAP importance, local SHAP bars, stability badges, layered disclosure (top 3 / 5), fairness cues |
| LLM | `llm` | Baseline + grounded summaries with evidence links, NL query (interpret → confirm → execute) |

XAI and LLM conditions require cached explanations (`python -m hc_analytics.explainability`). More UI detail: [frontend/README.md](frontend/README.md).

## Study instrumentation

When `HC_LOG_EVENTS=true` (default), the dashboard records telemetry to `artifacts/logs/`:

- `events.jsonl` — append-only event stream
- `events.sqlite` — indexed store for session export
- Pseudonymized session bundles via the **Export study session** toolbar button or `POST /api/instrumentation/export`

Assign a participant label with `http://localhost:5173/?participant=P001`. Events include session start, filter changes, drill-down, explanation views, NL query steps, exports, and latency payloads. Version context (model, explanation, API build) is attached server-side.

## Testing

```bash
cd backend && source .venv/bin/activate
pytest
```

## API overview

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Service health and active condition |
| `GET /api/meta` | Pipeline readiness and prototype metadata |
| `GET /api/cohort/summary` | Cohort aggregates for dashboard charts |
| `GET /api/beneficiaries` | Sortable risk table rows |
| `GET /api/beneficiaries/{id}` | Beneficiary drill-down |
| `GET /api/predictions` | Risk scores (legacy route; also used by tooling) |
| `GET /api/explanations/global` | Cohort-level SHAP importance (XAI) |
| `GET /api/explanations/{id}` | Local SHAP contributors (XAI) |
| `GET /api/language/summary/{id}` | Grounded narrative (LLM) |
| `POST /api/language/query/interpret` | Parse NL query (LLM) |
| `POST /api/language/query/execute` | Run confirmed query (LLM) |
| `POST /api/instrumentation/events` | Record study event |
| `POST /api/instrumentation/export` | Export pseudonymized session bundle |

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
| `docs/` | Architecture and data notes |

## Prototype status

**Complete (Phases 0–8):** scaffold → CMS ingestion → feature store → risk models → SHAP explainability → baseline dashboard → XAI UI → grounded language layer → instrumentation and study export.

## Data

Download CMS DE-SynPUF (or equivalent synthetic Medicare) files into `data/raw/`. See [docs/DATA.md](docs/DATA.md) for expected file layout and provenance tracking.

## Further reading

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layer design and experimental conditions
- [docs/DATA.md](docs/DATA.md) — raw file layout and artifact manifests
- [frontend/README.md](frontend/README.md) — per-condition UI behavior

## License

Research use. Not for clinical deployment.
