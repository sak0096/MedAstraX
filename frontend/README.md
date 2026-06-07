# Frontend

React + Vite + Plotly dashboard for three experimental conditions.

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
- `xai` — SHAP bars, global importance, stability badges (Phase 6)
- `llm` — grounded summaries, NL query with confirmation (Phase 7)

Set `HC_EXPERIMENTAL_CONDITION` in the backend `.env` to match the study arm.
