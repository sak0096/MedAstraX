# Frontend

React + Vite + Plotly dashboard for three experimental conditions.

## Phase 8 — Instrumentation

When `HC_LOG_EVENTS=true` (default), the dashboard records study events to `artifacts/logs/`:

- JSONL stream (`events.jsonl`) and SQLite index (`events.sqlite`)
- UI events: session start, filter changes, drill-down, explanation views, NL queries, exports
- Latency payloads for drill-down actions
- Pseudonymized session export via **Export study session** (toolbar) or `POST /api/instrumentation/export`

Pass `?participant=P001` in the URL to assign a participant ID for the session.

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

From the repo root (after `./scripts/setup.sh`):

```bash
./scripts/start-dashboard.sh
```

API only: `./scripts/dev.sh`. Open http://localhost:5173. Vite proxies `/api` and `/health` to the FastAPI service. See the root [README](../README.md) for the full first-time setup flow.

## Conditions

- `baseline` — cohort views, risk tables, drill-down, no explanation UI
- `xai` — SHAP bars, global importance, stability badges
- `llm` — grounded summaries, NL query with confirmation

Set `HC_EXPERIMENTAL_CONDITION` in the backend `.env` to match the study arm.
