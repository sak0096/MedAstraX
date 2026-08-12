# MedAstraX Study Documentation Index

Start here for human-participant research using the prototype.

## Conducting a session

1. **[FACILITATOR_RUNBOOK.md](./FACILITATOR_RUNBOOK.md)** — setup, consent, debrief, counterbalancing, troubleshooting
2. **[STUDY_PROTOCOL.md](./STUDY_PROTOCOL.md)** — design, tasks, manipulations, instrumentation
3. **[SURVEY_INSTRUMENTS.md](./SURVEY_INSTRUMENTS.md)** — Qualtrics item banks (external surveys)

## Analysis & reference

4. **[STUDY_APPENDICES.md](./STUDY_APPENDICES.md)** — RQ crosswalk, error catalog, scoring, event schema
5. **[README.md](../README.md)** — technical setup, APIs, `HC_STUDY_MODE`

## Technical artifacts

| File | Role |
|------|------|
| `study/study_cases.json` | Tasks, cases, ground truth, manipulations (v2.0) |
| `study/frozen_summaries.json` | Frozen Study 2 narratives (template or adjudicated LLM polish) |
| `study/adjudication_queue.json` | Human review queue when `HC_LLM_*` generates candidates |
| `scripts/generate_study_cases.py` | Regenerate catalog from parquet/SHAP |
| `scripts/generate_frozen_summaries.py` | Regenerate frozen summaries (`--require-llm` / `--allow-template`) |
| `scripts/apply_adjudication.py` | Apply accept/use_template decisions into frozen summaries |
| `scripts/score_study_session.py` | Behavioral reliance metrics from export |

## Readiness checklist

| Ready for | Requirements |
|-----------|--------------|
| **Formative pilot** | IRB submitted or exempt; facilitator runbook; `HC_STUDY_MODE=true`; Qualtrics draft |
| **Confirmatory collection** | IRB approved; pilot complete; preregistration; frozen protocol + survey versions |

Participant URLs: `?participant=P001&study=study1&condition=baseline` (then the other condition without restarting the API).
