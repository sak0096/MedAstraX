# MedAstraX Study Appendices

Companion to the revised dissertation proposal Appendices A, D, E, and F.  
**Catalog source of truth:** `study/study_cases.json` v2.0

---

## Appendix A — RQ → task → metric crosswalk

| RQ | Study | Task | Ground truth | Primary outcome | Analysis |
|----|-------|------|--------------|-----------------|----------|
| RQ1 | 1 | S1-T3 Risk drivers | Frozen SHAP top-3 | Interpretation accuracy | Logistic / ordinal mixed model |
| RQ1 | 1 | S1-T5 Outreach | Operational priority rule | Final accuracy; harmful switching | Mixed model + interaction (correct vs incorrect AI) |
| RQ2 | 2 | S2-T3 Summary | Structured record | Unsupported-claim detection | Logistic mixed model |
| RQ2 | 2 | S2-T3 Sequential | Task-specific key | Harmful adoption; final accuracy | Transition model |
| RQ3 | 2 | S2-T1 vs S2-T2 | Deterministic cohort set | Exact match; time | Mixed model; precision/recall secondary |
| RQ3 | 2 | S2-T2/S2-T6 Query | Parsed parameters | Reject/revise; result accuracy | Logistic mixed model |
| H1c | 1 | All S1 tasks | — | NASA-TLX, completion time | TLX mixed model |
| H3a | 2 | S2-T1 vs S2-T2 | Same cohort spec | Time among correct | Lognormal / Gamma mixed model |

**Exploratory (not primary):** S1-T1, S1-T4a, S1-T6, S2-T5, S2-T7.

---

## Appendix D — Controlled-error catalog

| Category | Example in MedAstraX | Validity requirement | Status |
|----------|---------------------|----------------------|--------|
| Incorrect outreach recommendation | M2 on S1-T5 — promotes low-priority case | Rule + record fields visible; initial/final ranks logged | **Primary** (~50% of participants) |
| Faithful outreach recommendation | `correct` on S1-T5 — matches priority rule | Same procedure; enables beneficial-correction analysis | **Primary** (~50% of participants) |
| Unsupported narrative claim | M3 on S2-T3 — false inpatient claim | Contradicts `inpatient_claims` etc.; evidence links work | **Primary** |
| Incorrect query condition | M4 — hypertension for diabetes | Interpretation card shows filter before execute | **Primary** |
| Incorrect query analytic year | M6 — substitutes 2021 for requested 2022 | Task text + interpretation card; changes executed annual cohort | **Primary** |
| Omitted query threshold | M7 — drops `min_total_claims` from card | Threshold in participant query string | **Primary** |
| Altered SHAP ranking | — | Excluded from v2 primary design | **Not used** |
| Arbitrary wrong risk score | — | Excluded from v2 primary design | **Not used** |

---

## Appendix E — Behavioral scoring

Implemented in `backend/src/hc_analytics/study/scoring.py` and `scripts/score_study_session.py`.

| Metric | Definition |
|--------|------------|
| **Correct-AI adherence** | Final response matches correct AI advice (faithful recommendation) |
| **Incorrect-AI adherence** | Final response matches manipulated AI advice |
| **Beneficial correction** | Initial wrong → final correct after correct AI |
| **Harmful switching** | Initial correct → final wrong after incorrect AI |
| **Appropriate rejection** | Incorrect AI rejected; final response correct |
| **Underreliance** | Correct AI available but final remains wrong |
| **Evidence inspection** | `evidence_link_open` before final response on S2-T3 |
| **Top-1 correct** | First-ranked ID matches the operational priority winner |
| **Kendall tau distance** | Normalized pairwise inversions between final ranking and ground truth |
| **Interpretation accuracy** | Feature+direction pairs vs SHAP top drivers (partial credit) |
| **Claim detection** | Unsupported judgment **and** flagged sentence matching the M3 statement |
| **Query set match** | Exact ID **set** match; ordered match secondary; precision/recall vs expected cohort |
| **Appropriate reliance index** | Correct-AI adherence (faithful trials) minus incorrect-AI adherence (manipulated trials) |
| **Harmful switching rate** | Among manipulated trials that were initially correct |
| **Beneficial correction rate** | Among faithful trials that were initially incorrect |

**Weight of Advice (WOA):** implemented in `scoring.py` for outreach ranks as movement from initial ranking toward the AI recommendation. Trials where the initial ranking equals the advice are left missing rather than given an arbitrary value.

**Appropriate reliance index (session-level):** agreement with correct AI minus agreement with incorrect AI across manipulation trials.

---

## Appendix F — Event schema

Each stored event includes:

| Field | Source |
|-------|--------|
| `event_type` | See list below |
| `timestamp` | UTC |
| `participant_id` | URL `?participant=` |
| `session_id` | Browser session storage |
| `study_id` | Config |
| `condition` | URL `?condition=` / `X-Study-Condition` (fallback: `HC_EXPERIMENTAL_CONDITION`) |
| `task_id` | Active Task Panel task |
| `payload` | Event-specific (includes `trial_id`, `phase`, `manipulation_type`, `ground_truth` when applicable) |
| `version_context` | Model, explanation, API build (server-enriched) |

### Event types

| Event | When |
|-------|------|
| `session_start` | Dashboard load |
| `task_start` | Task selected in panel |
| `task_initial_response` | Initial judgment submitted |
| `task_response` | Final or single-phase response |
| `comprehension_complete` | S1-T0 quiz submitted |
| `drill_down` | Beneficiary opened |
| `explanation_view` | SHAP loaded |
| `explanation_toggle` | Concise/expanded toggle |
| `evidence_link_open` | Summary source link clicked |
| `evidence_dwell` | Time spent after opening a source link |
| `query_submit` | NL query sent |
| `query_confirm` | Query executed |
| `query_reject` | Query cancelled |
| `query_revise` | Interpretation rejected in order to rephrase |
| `filter_change` | Table sort changed |
| `export` | CSV or summary export |
| `latency` | Timed action wrapper |

### Reconstructing a trial

Filter events by `payload.trial_id` (S1-T5, S2-T3). Order by `timestamp`. Join initial + final responses with `payload.ground_truth` on final event.

---

## Appendix G — Condition feature matrix

| Feature | Study 1 Baseline | Study 1 XAI | Study 2 Baseline | Study 2 NL-assisted |
|---------|------------------|-------------|------------------|-------------|
| Structured beneficiary record | Yes | Yes | Yes | Yes |
| Operational priority rule | Yes (S1-T0+) | Yes | — | — |
| Local SHAP | No | Yes (faithful) | No | No |
| Global SHAP | No | Tutorial only (S1-T4a) | No | No |
| AI outreach recommendation | On S1-T5 | On S1-T5 | — | — |
| Grounded narrative | No | No | No | Yes (frozen) |
| Evidence source links | Record panels | Record panels | Record panels | Yes |
| Manual filters / sort | Yes | Yes | Yes | Yes |
| NL query | No | No | No | Yes |
| Query confirmation | — | — | — | Yes |

## Appendix H — Study 2 language-stimulus provenance

| Component | Frozen implementation |
|-----------|-----------------------|
| Generation mode | Offline, before participant exposure; no live summary-generation call during a session |
| Cases | 12 prespecified beneficiary cases, analytic year 2022 |
| Grounding inputs | Calibrated risk estimates plus top-three local contributors for hospitalization, high utilization, and elevated cost |
| Named model | `gpt-4.1-2025-04-14` through OpenAI Chat Completions |
| Decode configuration | Temperature `0`; JSON narrative response |
| Prompt | `grounded-polish-v4`; three outcome-ordered sentences; exact risk percentages and driver directions; no raw driver values, causal wording, or model-family jargon |
| Frozen artifact | `study/frozen_summaries.json` with model, prompt, Git, prompt-hash, and evidence provenance |
| Automated evidence audit | 12/12 passed `scripts/audit_frozen_summaries.py`; recorded explicitly as `reviewer_type: "ai_assisted"` |
| Human adjudication | Required before confirmatory collection; currently recorded separately from the automated audit |
| Runtime query behavior | Deterministic keyword/regular-expression interpretation, participant confirmation, then execution over analytic tables |

The `llm` condition key therefore denotes the complete **NL-assisted interface condition**. It must not be interpreted as evidence that every language feature invokes a live LLM or that the experiment evaluates unconstrained LLM capability.

### Current frozen release

| Provenance field | Recorded value |
|------------------|----------------|
| Generated at | `2026-08-12T22:19:13.957198+00:00` |
| Generator code commit | `1348ec0e006139586e536f72875bfb0e5302a00b` |
| Frozen-artifact commit | `b521ce63f449c090c93e4d02c0d1955b69acbbe8` |
| Frozen-summary file fingerprint | `337c1dfcc92b86fa` (first 16 hexadecimal characters of SHA-256) |
| Study-case file fingerprint | `582f71bf02cccccc` (first 16 hexadecimal characters of SHA-256) |
| Summary count | 12 |
| Technical audit status | Complete; 12 accepted candidates and 0 template substitutions |
| Independent human review | Pending; required before confirmatory collection |

If the frozen summary or case file changes, these values must be regenerated and the change treated as a new stimulus release.
