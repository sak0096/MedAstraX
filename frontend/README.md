# Frontend

React + Vite + Plotly dashboard for three experimental conditions.

Implementation begins in **Phase 5** (baseline dashboard). The package manifest is included in Phase 0 so condition switching and API contracts can be designed against the backend from the start.

## Conditions

- `baseline` — cohort views, risk tables, drill-down, no explanation UI
- `xai` — SHAP bars, global importance, stability badges
- `llm` — grounded summaries, NL query with confirmation

Set `HC_EXPERIMENTAL_CONDITION` in the backend `.env` to match the study arm.
