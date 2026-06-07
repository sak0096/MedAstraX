# Frontend

React + Vite + Plotly dashboard for three experimental conditions.

## Phase 7 — LLM-augmented dashboard

Set `HC_EXPERIMENTAL_CONDITION=llm` in the backend `.env`.

The LLM condition adds:

- Grounded beneficiary summaries from SHAP evidence bundles
- Evidence links showing source fields behind each claim
- Natural-language query box with interpret → confirm → execute flow
- SQLite query cache (`artifacts/query_cache/`)
- Template provider by default; set `HC_LLM_*` env vars for external LLM config

## Phase 6 — XAI-augmented dashboard

Set `HC_EXPERIMENTAL_CONDITION=xai` in the backend `.env`.

The XAI condition adds to the baseline layout:

- Global SHAP importance panel with target switching
- Local SHAP bar charts in beneficiary drill-down
- Stability badges (green / yellow / red)
- Layered disclosure toggle (top 3 vs top 5)
- Fairness cues on equity-relevant features (age, sex, race, state, ESRD)
- Contextual value previews mapped to beneficiary fields

## Phase 5 — Baseline dashboard

The baseline condition provides:

- Cohort overview charts (age, chronic conditions, utilization, cost)
- Sortable risk table with hospitalization, high-utilization, and elevated-cost scores
- Beneficiary drill-down (demographics, utilization, diagnosis profile)
- CSV export for the risk table and printable cohort summary (PDF via browser print)

## Run locally

```bash
# Terminal 1 — backend API
cd backend && source .venv/bin/activate
uvicorn hc_analytics.api.app:app --reload

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` and `/health` to the FastAPI service.

## Conditions

- `baseline` — cohort views, risk tables, drill-down, no explanation UI
- `xai` — SHAP bars, global importance, stability badges
- `llm` — grounded summaries, NL query with confirmation

Set `HC_EXPERIMENTAL_CONDITION` in the backend `.env` to match the study arm.
