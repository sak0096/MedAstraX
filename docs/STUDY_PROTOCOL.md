# MedAstraX User Study Protocol

**Dissertation:** *Human-Centered Explainable AI for Healthcare Analytics* (revised proposal)  
**Instrument:** MedAstraX research prototype (CMS Synthetic RIF)  
**Conditions:** `baseline` · `xai` · `llm`  
**Catalog schema:** `study/study_cases.json` v2.0  
**Protocol version:** 2.0

---

## 1. Study overview

Two **separate** controlled component evaluations share the same prototype but use **independent participant samples**:

| Study | Comparison | Primary RQs |
|-------|------------|-------------|
| **Study 1** | Baseline vs XAI | RQ1 — interpretation accuracy, workload, harmful switching on incorrect AI recommendation |
| **Study 2** | Baseline navigation vs LLM | RQ2–RQ3 — unsupported-claim detection, query control, NL efficiency |

**Within each study:** within-subjects, counterbalanced condition order (Baseline first vs AI-augmented first), mixed methods (behavioral logs + validated scales + interview).

**Not in scope:** direct XAI vs LLM comparison (separate studies by design).

**Sample (target):** *n* ≈ 40–50 per study. Recruit Study 1 and Study 2 cohorts separately.

**Eligibility:** ≥2 years in healthcare analytics, care coordination, utilization management, or clinical decision support; routine dashboard/EHR familiarity.

---

## 2. Materials

| Material | Location / delivery |
|----------|---------------------|
| Consent & debrief | [FACILITATOR_RUNBOOK.md](./FACILITATOR_RUNBOOK.md) §2–3 |
| Scenario framing | §5 below; read aloud at orientation |
| Case packets & ground truth | `study/study_cases.json` (regenerate via `scripts/generate_study_cases.py`) |
| Frozen LLM stimuli | `study/frozen_summaries.json` |
| In-app tasks | Task Panel (`HC_STUDY_MODE=true`) |
| Post-condition surveys | [SURVEY_INSTRUMENTS.md](./SURVEY_INSTRUMENTS.md) — **Qualtrics** (external) |
| Exit interview | SURVEY_INSTRUMENTS Part D |
| Event logs | `artifacts/logs/` + **Export study session** button |
| Scoring | `scripts/score_study_session.py` |

**Participant URL (production):**

```
http://localhost:5173/?participant=P001&study=study1&condition=baseline
http://localhost:5173/?participant=P001&study=study1&condition=xai
http://localhost:5173/?participant=P001&study=study2&condition=baseline
http://localhost:5173/?participant=P001&study=study2&condition=llm
```

Condition is session-scoped via the `condition` query param (and `X-Study-Condition` header). Do not restart the API to switch blocks. Case set α/β flips across the two blocks. Study 1 assigns complementary faithful vs M2 outreach across the two conditions. Study 2 assigns M3, M4/M6/M7, and T6 independently per task.

**Facilitator URL (shows manipulation assignments):** add `&facilitator=1`.

**Do not use** `study=full` with participants — facilitator/engineering only.

**Condition:** pass `condition=baseline|xai|llm` on the participant URL. `HC_EXPERIMENTAL_CONDITION` is only a fallback when the URL/header is omitted.

---

## 3. Session flows

### 3.1 Study 1 session (~45–55 min)

| Step | Duration | Activity |
|------|----------|----------|
| 0 | 5 min | Consent, demographics (Qualtrics Part A) |
| 1 | 3 min | Scenario orientation; open dashboard **Condition A** |
| 2 | 5 min | **S1-T0** — priority rule tutorial + in-app comprehension check |
| 3 | 20 min | Study 1 tasks (S1-T1 … S1-T6 per condition filter) |
| 4 | 5 min | Post-condition survey (Qualtrics Part B) |
| 5 | 5 min | Break; switch to **Condition B** (`?condition=` on the same participant URL) |
| 6 | 20 min | Repeat tasks in second condition |
| 7 | 5 min | Post-condition survey (Part B, second condition) |
| 8 | 5 min | Study 1 post-study block (Qualtrics Part C — Study 1 version) |
| 9 | 10 min | Exit interview (Part D) |
| 10 | 3 min | Debrief; export session log |

### 3.2 Study 2 session (~45–55 min)

| Step | Duration | Activity |
|------|----------|----------|
| 0 | 5 min | Consent, demographics (Part A) |
| 1 | 3 min | Scenario orientation; open dashboard **Condition A** |
| 2 | 5 min | **S2-T0** — query/filter tutorial + in-app comprehension check |
| 3 | 20 min | Study 2 tasks for Condition A |
| 4 | 5 min | Post-condition survey (Part B) |
| 5 | 5 min | Break; switch to **Condition B** (`?condition=` on the same participant URL) |
| 6 | 20 min | Repeat Study 2 tasks in second condition |
| 7 | 5 min | Post-condition survey (Part B) |
| 8 | 5 min | Study 2 post-study block (Part C — Study 2 version) |
| 9 | 10 min | Exit interview |
| 10 | 3 min | Debrief; export session log |

### 3.3 Counterbalancing

- **Study 1:** 50% Baseline→XAI, 50% XAI→Baseline (shown as `recommended_first_condition` on the session API).
- **Study 2:** 50% Baseline→LLM, 50% LLM→Baseline.
- **Case set:** α vs β assigned to block 1 vs block 2 (not reused across conditions).
- **Manipulations:** Study 1 complementary faithful/M2 across conditions; Study 2 per-task M3 / query error / optional second query error.

### 3.4 Facilitator script anchors

- “You are a care manager at a regional ACO reviewing **synthetic** Medicare utilization data.”
- “Risk scores are model estimates, not diagnoses.”
- “Use what you see in the dashboard; you may take notes.”
- “Some system outputs may be inaccurate — verify against the record when it matters.” *(IRB-approved general warning; do not reveal error placement.)*
- Do **not** name SHAP, LLM architecture, or intentional error trials until debrief.

---

## 4. Controlled errors (Appendix D)

| ID | Error | Study | Task | Measurement |
|----|-------|-------|------|-------------|
| **M2** | Incorrect **outreach recommendation** vs operational priority rule | 1 | S1-T5 | Harmful switching, appropriate rejection |
| **M3** | Unsupported grounded narrative claim | 2 | S2-T3 | Claim flagging, evidence-link opens |
| **M4** | Wrong NL chronic filter (e.g., diabetes→hypertension) | 2 | S2-T2, S2-T6 | `query_reject`, correction |
| **M6** | Wrong analytic year (2021 substituted for requested 2022) | 2 | S2-T2, S2-T6 | `query_reject` |
| **M7** | Omitted utilization threshold on interpretation card | 2 | S2-T2, S2-T6 | `query_reject` |

**Excluded from primary design:** inverted SHAP, arbitrary wrong risk scores, confidence-framing-only manipulations.

**Faithful stimuli:** local SHAP on S1-T3; frozen summaries on S2-T3+; priority rule fields on beneficiary panels.

**Study 1 outreach counterbalancing:** each participant sees a **faithful** recommendation in one condition and **M2** in the other (XOR across blocks). Enables harmful-switching (incorrect AI) and beneficial-correction (faithful AI) within the same person.

### 4.1 Sequential judgment (S1-T5, S2-T3)

1. **Initial** response + confidence (1–7) + reliance source — logged as `task_initial_response`
2. AI assistance (outreach recommendation panel or drill-down summary)
3. **Final** response + confidence + reliance source — logged as `task_response` with ground-truth payload

### 4.2 Operational priority rule (Study 1)

Taught in **S1-T0** comprehension gate. Weights:

| Signal | Weight |
|--------|--------|
| Inpatient claims | ×3 |
| Outpatient claims | ×0.5 |
| Chronic condition count | ×2 |
| Total claims (analytic year) | ×0.1 |

Higher score → higher outreach priority. Ground truth rankings in `study_cases.json` → `ground_truth.outreach_set_ranking`.

---

## 5. Scenario framing

**Organization:** Fictional “Lakeview ACO Care Management.”  
**Goal:** Prioritize beneficiaries for proactive outreach using hospitalization, high-utilization, and elevated-cost risk.  
**Data:** CMS Synthetic RIF — demographics, claims, Part D, chronic flags, utilization, costs, model risk scores.

Participants treat the dashboard as **decision support**, not bedside diagnosis.

---

## 6. Study 1 tasks

**Block intro:** “Review cohort and beneficiary records to identify who needs outreach and why. In the XAI version, explanation panels may appear — use them if helpful.”

| ID | Title | Time | Conditions | Notes |
|----|-------|------|------------|-------|
| **S1-T0** | Priority rule tutorial | 4 min | All | Comprehension gate; blocks other tasks until passed |
| **S1-T1** | Cohort situational awareness | 4 min | All | Exploratory; cohort charts only |
| **S1-T2** | High-risk identification | 5 min | All | Sort risk table; top 5 IDs |
| **S1-T3** | Risk driver interpretation | 6 min | All | Case **B-07**; **faithful SHAP** in XAI; no manipulation |
| **S1-T4a** | Global model literacy | 5 min | XAI only | **Tutorial/exploratory** — not primary RQ |
| **S1-T4b** | Clinical judgment | 5 min | Baseline only | Case **B-12**; profile panels only |
| **S1-T5** | Outreach prioritization | 8 min | All | **Sequential ranking**; α/β case quartet; **faithful or M2** recommendation (~50/50) |
| **S1-T6** | Explanation density | 4 min | XAI only | **Exploratory** — Case B-09 |

### S1-T5 procedure (facilitator)

1. Participant completes **initial** ranking of assigned quartet (B-01…B-04 or B-01b…B-04b).
2. Participant clicks **Show AI recommendation**.
3. Participant submits **final** ranking with confidence and reliance source.
4. Facilitator ensures cases were opened for verification as needed.

**Ground truth:** operational priority rule ranking in `study_cases.json`, not raw hospitalization risk alone.

---

## 7. Study 2 tasks

**Block intro:** “This version may show written summaries and a natural-language query box. Confirm queries before running them. Validate answers against the underlying data.”

| ID | Title | Time | Conditions | Notes |
|----|-------|------|------------|-------|
| **S2-T1** | Manual cohort filtering | 5 min | Baseline | Top 25 by Hosp. risk + diabetes; no query box |
| **S2-T2** | NL cohort query | 5 min | LLM | Suggested query includes analytic year 2022 + claim threshold; **M4/M6/M7** |
| **S2-T3** | Summary validation | 8 min | LLM | Case **B-15**; **sequential** claim review; **M3** |
| **S2-T4** | Cross-check summary vs record | 5 min | All | Case B-15 |
| **S2-T5** | Cohort analytics query | 6 min | LLM | Cohort summary NL query |
| **S2-T6** | Query control check | 5 min | LLM | Heart failure query; reject if misparsed |
| **S2-T7** | Export and handoff | 3 min | All | CSV + printable summary |

### S2-T2 / S2-T6 suggested queries (from catalog)

- S2-T2: `Top 25 hospitalization risk with diabetes in analytic year 2022 with at least 50 claims`
- S2-T6: `Top 10 elevated cost risk with heart failure in analytic year 2022 with at least 30 claims`

The source features are beneficiary-year aggregates. Query tasks therefore use an explicit analytic year; they do not claim support for rolling month windows.

Participant must review interpretation card before confirming. Cancel/rephrase logs `query_reject`.

---

## 8. Case packets

Regenerate after pipeline runs:

```bash
source backend/.venv/bin/activate
python scripts/generate_study_cases.py
python scripts/generate_frozen_summaries.py
```

| Field | Source |
|-------|--------|
| `bene_id`, utilization, chronic flags | `feature_store.parquet` |
| Risk scores | `predictions.parquet` |
| Top SHAP features | `artifacts/explanations/local_topk.parquet` |
| Priority scores & outreach rankings | Computed in generator via `priority.py` |
| Manipulation configs | Per-case `manipulations` block |
| Parallel sets | `case_sets.alpha` / `case_sets.beta` |

---

## 9. Instrumentation

| Measure | Logged | Event / field |
|---------|--------|---------------|
| Session start | Yes | `session_start` |
| Task start | Yes | `task_start` + `trial_id` |
| Initial judgment | Yes | `task_initial_response` + `phase`, `confidence` |
| Final judgment | Yes | `task_response` + `ground_truth` on S1-T5 final |
| Comprehension | Yes | `comprehension_complete` |
| Sort / filter | Yes | `filter_change` |
| Drill-down | Yes | `drill_down`, `latency` |
| Explanation view | Yes | `explanation_view`, `explanation_toggle` |
| Evidence link click | Yes | `evidence_link_open` |
| Evidence dwell | Yes | `evidence_dwell` (`duration_ms`) |
| NL query | Yes | `query_submit`, `query_confirm`, `query_reject`, `query_revise` |
| Export | Yes | `export` |
| Active task context | Yes | `X-Study-Task-Id` header on API calls |
| Manipulation type | Yes | Server-side in event payload; hidden from participant UI |

**End of session:** Events autosave every 30s; the toolbar button downloads a snapshot. Files land in `artifacts/logs/exports/`.

**Scoring:**

```bash
python scripts/score_study_session.py <session_id>
```

See [STUDY_APPENDICES.md](./STUDY_APPENDICES.md) for behavioral metric definitions.

### Known limitations

- Surveys are external (Qualtrics), not embedded in-app.
- Time limits are logged (`timed_out`) but not hard-stopped in the UI.
- Explanation density (S1-T6) remains exploratory; confirmatory XAI uses the concise top-3 display plus optional expansion.
- Feature-dominance badges remain in the XAI UI (top-contribution gap; not perturbation stability). Bootstrap stability code exists but is not the production method.
- Operational priority rule is frozen: inpatient×3, outpatient×0.5, chronic×2, total_claims×0.1.
- Study 2 condition key remains `llm`, but participant-facing chrome stays neutral. The committed summaries are grounded, named-model-polished stimuli with an automated evidence audit; `study/frozen_summaries.json` records the exact model and prompt. Independent human adjudication is still required before confirmatory use (`study/adjudication_queue.json`, then `scripts/apply_adjudication.py --require-complete`). Treat the intervention as grounded natural-language augmentation, not a general LLM-capability evaluation.
- Risk percentages are produced from a **calibrated XGBoost** artifact (temporal calib year + isotonic). Keep `HC_ALLOW_LOGISTIC_FALLBACK=false`. On a fresh Mac without Homebrew OpenMP, run `./scripts/ensure_xgboost_libomp.sh` after `./scripts/setup.sh`.
- High-utilization and elevated-cost label thresholds are frozen from the model training years only and recorded, with their source years, in model metadata and `artifacts/model_manifest.json`.
- Study-case explanation badges use bootstrap top-feature agreement when `HC_STABILITY_METHOD=bootstrap`; bulk rows still use dominance margin for cost. SHAP background sampling uses train years from the model metadata.
- Docker/`docker-compose` provides a localhost-to-cloud packaging scaffold; online recruitment still needs HTTPS, durable Postgres event storage, and auth.
- Instrumentation `version_context` now records model family plus artifact hashes for models, explanations, and frozen study files.
- Prefer Python 3.12 (CI/Docker/`.python-version`). Local 3.9 still runs tests; several audited package fixes require ≥3.10 and should be applied when upgrading the local venv.
- Remaining npm audit findings are Vite/esbuild dev-server advisories; leave Vite 5 unless you intentionally upgrade to Vite 8.
- Cloud hosting (HTTPS, Postgres events, auth) remains deferred.

---

## 10. Analysis reminders

- **Primary:** interpretation accuracy (S1-T3), harmful switching (S1-T5), unsupported-claim detection (S2-T3), query accuracy + reject rate (S2-T2/S2-T6).
- **Models:** logistic mixed-effects; participant and case random effects where preregistered.
- **Secondary:** NASA-TLX, SUS, trust scale, perceived understanding/control.
- **Exploratory:** S1-T4a, S1-T6, subgroup/moderator analyses — label explicitly.
- **Do not** compare XAI vs LLM across studies as causal evidence.

---

## 11. Ethics

- Obtain **IRB approval** before any human-participant activity (including pilots).
- Consent must describe experimental interfaces, recording, synthetic data, and that outputs **may be inaccurate** (IRB-approved wording).
- **Do not** disclose which trials contain intentional errors until debrief (unless IRB requires otherwise).
- Debrief: reveal error types, synthetic data, non-evaluative framing — see [FACILITATOR_RUNBOOK.md](./FACILITATOR_RUNBOOK.md).
- Store pseudonymized logs; separate participant code key.
- Preregister after formative pilot: outcomes, models, exclusions, manipulation rate.

---

## 12. Related documents

| Document | Purpose |
|----------|---------|
| [FACILITATOR_RUNBOOK.md](./FACILITATOR_RUNBOOK.md) | Step-by-step conduct, consent/debrief, counterbalancing |
| [SURVEY_INSTRUMENTS.md](./SURVEY_INSTRUMENTS.md) | Qualtrics item banks |
| [STUDY_APPENDICES.md](./STUDY_APPENDICES.md) | Error catalog, scoring, event schema, RQ crosswalk |
| [README.md](../README.md) | Technical setup and API reference |
