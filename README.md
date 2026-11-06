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

- Python **3.9.6** (see `.python-version`; 3.9+ supported)
- Node.js **24.16.0** and npm (see `.nvmrc`; installed automatically by `./scripts/setup.sh` via nvm if missing)
- CMS synthetic files staged under `data/raw/` ([CMS Synthetic RIF collection](https://data.cms.gov/collection/synthetic-medicare-enrollment-fee-for-service-claims-and-prescription-drug-event); see [docs/DATA.md](docs/DATA.md))
- macOS only: `brew install libomp` if you want XGBoost training alongside logistic regression

## Reproducible setup

### First-time workflow (fresh clone)

```bash
git clone <repo-url> MedAstraX && cd MedAstraX

./scripts/setup.sh          # .env, Python venv, pinned deps, npm ci (installs nvm/Node if needed)
# optional: edit .env — HC_EXPERIMENTAL_CONDITION is a fallback if the URL omits condition=

# Stage CMS synthetic files under data/raw/ (see docs/DATA.md), then:
source backend/.venv/bin/activate
python -m hc_analytics.ingestion
python -m hc_analytics.features
python -m hc_analytics.modeling
python -m hc_analytics.explainability
# faster dev iteration (partial SHAP cache):
# python -m hc_analytics.explainability --max-rows 1000

./scripts/verify.sh         # pytest + frontend build + API smoke check
./scripts/start-dashboard.sh
```

Open http://localhost:5173 for local development. Vite proxies `/api` and
`/health` to FastAPI. Strict study sessions are entered through the
authenticated launch/exchange flow; URL participant/condition values are only
legacy local-development context and are not authorization.

Check readiness anytime: `GET http://127.0.0.1:8000/api/meta` (data, models, predictions, explanations, instrumentation flags).

Processed outputs land in `data/processed/`. Models, explanations, and logs are written under `artifacts/` (gitignored).

### Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup.sh` | Idempotent install: `.env`, backend venv, `requirements-lock.txt`, `npm ci` |
| `scripts/verify.sh` | Run tests, production frontend build, and API smoke checks |
| `scripts/start-dashboard.sh` | Start API + Vite dev server together (runs `setup.sh` if deps are missing) |
| `scripts/dev.sh` | API only (auto-installs backend deps if needed) |
| `scripts/lock-deps.sh` | Regenerate `requirements-lock.txt` and `package-lock.json` after dep changes |

### Lockfiles

| File | Purpose |
|------|---------|
| `backend/pyproject.toml` | Python dependency ranges (source of truth) |
| `backend/requirements-lock.txt` | Pinned Python versions for `pip install -r` |
| `frontend/package.json` | Frontend dependency ranges |
| `frontend/package-lock.json` | Pinned npm versions for `npm ci` |
| `.python-version` | pyenv / local Python hint |
| `.nvmrc` | nvm Node version |
| `.env.example` | Committed environment template → copied to `.env` |

After changing `pyproject.toml` or `package.json`:

```bash
./scripts/lock-deps.sh
```

### Manual setup (equivalent to `setup.sh`)

```bash
cp .env.example .env
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-lock.txt && pip install -e ".[dev]"
cd ../frontend && npm ci
```

## Study conditions

For strict sessions, condition order and case set are assigned and bound by the
server. `condition=baseline|xai|llm`, `X-Study-Condition`, and
`HC_EXPERIMENTAL_CONDITION` remain local-development compatibility inputs only.

| Condition | URL value | Dashboard affordances |
|-----------|-----------|------------------------|
| Control | `baseline` | Cohort charts, sortable risk table, beneficiary drill-down, CSV/PDF export |
| XAI | `xai` | Baseline + global SHAP importance, local SHAP bars, stability badges, layered disclosure (top 3 / 5), fairness cues |
| NL-assisted (`llm` key) | `llm` | Baseline + grounded summaries with evidence links, NL query (interpret → confirm → execute) |

The Study 2 URL key remains `llm` for compatibility. The committed stimuli are grounded natural-language augmentation polished with the named model recorded in `study/frozen_summaries.json`. The automated evidence audit does not replace human adjudication: confirmatory use still requires a human to review `study/adjudication_queue.json` and run `scripts/apply_adjudication.py --require-complete`.

XAI and NL-assisted conditions require cached explanations (`python -m hc_analytics.explainability`). More UI detail: [frontend/README.md](frontend/README.md).

## Study instrumentation

When `HC_LOG_EVENTS=true` (default), the dashboard records telemetry to `artifacts/logs/`:

- local compatibility: `events.jsonl` and `events.sqlite`;
- strict/production sessions: canonical PostgreSQL events;
- authenticated research export only; participant study mode hides export UI.

Events include server-owned task/progression facts and allowed interaction
telemetry. Browser clients cannot submit critical task/comprehension events in
strict mode. Version context is attached server-side.

## User study mode

Enable the guided study protocol and manipulation trials:

```bash
# in .env
HC_STUDY_MODE=true
```

Use an authenticated synthetic launch (`namespace=test`) and exchange its
one-time token. The public `facilitator` query does not reveal assignments.
See [docs/QUALTRICS_INTEGRATION.md](docs/QUALTRICS_INTEGRATION.md).

Case packets live in [`study/study_cases.json`](study/study_cases.json) (schema
`3.0-october-working-counterpart`). Frozen Study 2 narratives:
[`study/frozen_summaries.json`](study/frozen_summaries.json). Regenerate after
pipeline runs:

```bash
source backend/.venv/bin/activate
python -m hc_analytics.explainability --study-cases-only   # or full cohort without the flag
python scripts/generate_study_cases.py
python scripts/generate_frozen_summaries.py --allow-template
# Optional named-model polish (requires HC_LLM_* + human review):
# python scripts/generate_frozen_summaries.py --require-llm
# python scripts/audit_frozen_summaries.py --record-decisions  # AI-assisted precheck only
# have a person review every item; set reviewer_type="human", then:
# python scripts/apply_adjudication.py --require-complete
```

Score a completed session:

```bash
python scripts/score_study_session.py <session_id>
```

**Current study documentation:** [docs/STUDY_INDEX.md](docs/STUDY_INDEX.md)
(hub) · [STUDY_CROSSWALK](docs/STUDY_CROSSWALK.md) ·
[QUALTRICS_INTEGRATION](docs/QUALTRICS_INTEGRATION.md) ·
[IRB_ALIGNMENT_AND_DECISIONS](docs/IRB_ALIGNMENT_AND_DECISIONS.md)

Study APIs (when `HC_STUDY_MODE=true`):

| Endpoint | Purpose |
|----------|---------|
| `GET /api/study/session` | Participant-safe case set, priority rule and comprehension |
| `GET /api/study/tasks` | Task definitions |
| `POST /api/study/tasks/{id}/start` | Begin task; returns `trial_id` for sequential tasks |
| `POST /api/study/tasks/{id}/response` | Submit initial/final/single-phase response |
| `GET /api/study/tasks/{id}/recommendation` | Outreach AI recommendation (Study 1) |
| `POST /api/study/comprehension` | Comprehension check (S1-T0) |
| `POST /api/study/score-session` | Authenticated behavioral reliance scoring |
| `POST /api/integration/launch` | Authenticated survey launch |
| `POST /api/integration/exchange` | One-time browser session exchange |
| `POST /api/integration/survey-callback` | Authenticated survey stage callback |

Primary controlled errors (revised proposal Appendix D): **M2** incorrect outreach recommendation, **M3** unsupported narrative, **M4/M6/M7** query interpretation errors. SHAP remains faithful during interpretation tasks.

## Testing

```bash
./scripts/verify.sh
# or backend only:
cd backend && source .venv/bin/activate && pytest
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
| `GET /api/study/session` | Study session assignments (requires `HC_STUDY_MODE`) |
| `GET /api/study/tasks` | Study task definitions |
| `POST /api/study/tasks/{id}/start` | Start guided task |
| `POST /api/study/tasks/{id}/response` | Submit initial/final task response |
| `GET /api/study/tasks/{id}/recommendation` | Outreach recommendation |

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
| `docs/` | Architecture, data notes, **study protocol & facilitator runbook** |

## Prototype status

The repository contains an engineering foundation for synthetic technical
validation. Participant recruitment is disabled. It is not pilot-ready without
the exact reviewed source comparison, final assets, actual QSF/branch evidence,
human adjudication, Azure/identity approval and validation, policy decisions,
container smoke, and signed release manifest. See
[docs/IRB_ALIGNMENT_AND_DECISIONS.md](docs/IRB_ALIGNMENT_AND_DECISIONS.md).

## Data

The prototype uses **CMS Synthetic Medicare Enrollment, FFS Claims, and PDE** (Synthetic RIF): synthetic enrollment snapshots, fee-for-service claims (inpatient, outpatient, carrier, SNF, DME, HHA, hospice), and Part D prescription events (~8,671 beneficiaries; 2015–2025 enrollment, 2015–2023 claims). Raw files are pipe-delimited CSVs staged under `data/raw/`.

Download from the [CMS data collection](https://data.cms.gov/collection/synthetic-medicare-enrollment-fee-for-service-claims-and-prescription-drug-event). See [docs/DATA.md](docs/DATA.md) for the exact file layout, ingestion steps, and provenance tracking.

## Further reading

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layer design and experimental conditions
- [docs/DATA.md](docs/DATA.md) — raw file layout and artifact manifests
- [frontend/README.md](frontend/README.md) — per-condition UI behavior
- [docs/BASELINE_AUDIT_2026-11-06.md](docs/BASELINE_AUDIT_2026-11-06.md) — reproduced audit
- [docs/STUDY_CROSSWALK.md](docs/STUDY_CROSSWALK.md) — October task/field/scoring map
- [docs/AZURE_DEPLOYMENT.md](docs/AZURE_DEPLOYMENT.md) — deployment/recovery runbook

## License

Research use. Not for clinical deployment.
