# MedAstraX Study Documentation Index

This checkout is approved only for synthetic engineering work. It is not ready
for human-participant recruitment.

## Current operating documents

1. **[APPROVED_SOURCE_MANIFEST.md](./APPROVED_SOURCE_MANIFEST.md)** — supplied
   authority package and exact-evidence gaps.
2. **[STUDY_CROSSWALK.md](./STUDY_CROSSWALK.md)** — October task, response,
   event and scoring contract.
3. **[QUALTRICS_INTEGRATION.md](./QUALTRICS_INTEGRATION.md)** — authenticated
   survey launch/callback and branch matrix.
4. **[ASYNC_STUDY_OPERATIONS.md](./ASYNC_STUDY_OPERATIONS.md)** — test/pilot
   namespaces, incidents and evidence packet.
5. **[IRB_ALIGNMENT_AND_DECISIONS.md](./IRB_ALIGNMENT_AND_DECISIONS.md)** —
   alignment, unresolved owners and release gates.
6. **[AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md)** — deployment, monitoring,
   backup/restore and rollback runbook.

`FACILITATOR_RUNBOOK.md`, `STUDY_PROTOCOL.md`, and `STUDY_APPENDICES.md` are
archived prototype documents. Their URL assignment and extra tasks are not an
operational protocol.

## Technical artifacts

| File | Role |
|------|------|
| `study/study_cases.json` | October working task catalog (schema `3.0-october-working-counterpart`) |
| `study/frozen_summaries.json` | Frozen Study 2 narratives (template or adjudicated LLM polish) |
| `study/adjudication_queue.json` | Human review queue when `HC_LLM_*` generates candidates |
| `scripts/generate_study_cases.py` | Regenerate catalog from parquet/SHAP |
| `scripts/generate_frozen_summaries.py` | Regenerate frozen summaries (`--require-llm` / `--allow-template`) |
| `scripts/audit_frozen_summaries.py` | Validate the three-outcome evidence contract; optional AI-assisted precheck |
| `scripts/apply_adjudication.py` | Apply accept/use_template decisions into frozen summaries |
| `scripts/score_study_session.py` | Behavioral reliance metrics from export |

## Readiness checklist

| Ready for | Current status |
|-----------|----------------|
| **Local synthetic engineering** | Conditional go; no participant data |
| **Deployed TEST validation** | No-go pending institutional Azure choices, assets, QSF and deployment evidence |
| **Covered pilot** | No-go; all pilot gates in the decision register must close |
| **Confirmatory collection** | No-go; requires completed pilot, final methods and approvals |

Current Study 2 narratives are pinned to the model and prompt version recorded in `study/frozen_summaries.json`. The AI-assisted evidence audit is complete; `human_adjudication_required` remains true until a person reviews every queue item, records `reviewer_type: "human"`, and reruns `scripts/apply_adjudication.py --require-complete`.

Participant identity, study, condition, case set and progression are
server-owned. Public URL/header values and `facilitator=1` are not
authorization.
