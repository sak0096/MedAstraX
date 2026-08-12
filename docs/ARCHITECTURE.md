# Architecture

This document summarizes the prototype architecture from the dissertation proposal and high-level design chapter. It is the implementation reference for this repository.

## Layers

### 1. Data Ingestion

Acquire CMS synthetic Medicare files, parse delimited flat files, validate schema, and emit:

- `beneficiaries` — enrollment-style demographics
- `claims` — fee-for-service utilization records
- `prescription_events` — pharmacy events

Preserve provenance: source file, extraction date, transformation version.

### 2. Feature Engineering

Produce beneficiary-period features for modeling and dashboards:

- utilization counts (inpatient, outpatient, physician, ER)
- diagnosis/chronic-condition indicators
- prescription burden
- rolling cost aggregates
- comorbidity-style indices
- readmission/hospitalization proxies

Also compute cohort summaries for dashboard overviews.

### 3. Modeling

Train versioned tabular models for operational risk tasks:

- next-period hospitalization risk
- high-utilization risk
- elevated cost risk

Primary families: logistic regression (interpretable baseline), XGBoost (stronger performance).

Each model artifact records: training date, feature set, target definition, split spec, metrics, model ID.

### 4. Explainability

Generate artifacts for the XAI condition and evidence bundles for the language layer:

- local SHAP (top-K contributors, direction of effect)
- global feature importance
- explanation stability indicators
- JSON evidence bundles per beneficiary/cohort

### 5. Grounded Language

Controlled orchestration — not an unconstrained chatbot:

- **Freeze-time grounded summaries:** deterministic evidence templates are polished offline with the named model recorded in `study/frozen_summaries.json`; participant sessions retrieve the frozen narrative rather than calling an LLM
- **Evidence contract:** each narrative retains the three risk percentages and top-three driver labels/directions for each outcome, with source mappings available through evidence links
- **Quality gates:** prompt/evidence hashes, automated contract audit, explicit AI-versus-human reviewer type, and template fallback on insufficient evidence
- **Runtime NL queries:** deterministic keyword/regular-expression interpretation → structured parameters → user confirmation → execute over analytic tables → charts + grounded summary

### 6. UI + Instrumentation

React dashboard with three conditions sharing layout and task environment.

Log: task metadata, interface events, explanation interactions, latency/fallback events, model and explanation versions.

## Core logical tables

| Table | Role |
|-------|------|
| `beneficiaries` | One row per beneficiary |
| `claims` | Claim/service facts |
| `prescription_events` | Medication events |
| `feature_store` | Engineered beneficiary-period features |
| `predictions` | Risk scores + model version |
| `explanations` | Local/global XAI artifacts |
| `query_cache` | NL query results + interpreted parameters |

## Experimental conditions

All conditions share data, models, and tasks. Only explanation/interaction affordances differ:

- **baseline** — risk scores, no explicit rationale UI
- **xai** — SHAP bars, global importance (tutorial tasks), stability badges
- **llm** — legacy condition key for the NL-assisted arm: frozen named-model-polished summaries, deterministic NL-query interpretation with confirmation, and evidence links

## User study mode (v2)

When `HC_STUDY_MODE=true`, the prototype adds:

- **Study orchestration** — `study/study_cases.json` task catalog, parallel case sets α/β, comprehension gate
- **Sequential judgments** — initial → AI → final on outreach and summary validation
- **Controlled errors** — M2 recommendation, M3/M4/M6/M7 query and narrative errors (Appendix D)
- **Instrumentation** — task events, evidence-link opens, session export, scoring script

Documentation: [STUDY_PROTOCOL.md](./STUDY_PROTOCOL.md), [FACILITATOR_RUNBOOK.md](./FACILITATOR_RUNBOOK.md), [STUDY_APPENDICES.md](./STUDY_APPENDICES.md).

## Versioning

Track versions for: data snapshot, feature logic, model config, explanation logic, language model snapshot and temperature, actual prompt/evidence hashes, frozen-summary hash, query parser, dashboard build, and adjudication status.
