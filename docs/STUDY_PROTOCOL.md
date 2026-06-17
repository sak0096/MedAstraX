# MedAstraX User Study Protocol

**Dissertation:** *Human-Centered Explainable AI for Healthcare Analytics*  
**Instrument:** MedAstraX research prototype (CMS Synthetic RIF, ~8,671 beneficiaries, 2015–2023 claims)  
**Conditions:** `baseline` · `xai` · `llm`  
**Version:** 2.0 (aligned with revised dissertation proposal — sequential judgments, Appendix D error catalog)

---

## 1. Study overview

This protocol operationalizes the dissertation’s two within-subjects experiments on the MedAstraX prototype. All conditions share the same underlying data, models, and layout; only explanation affordances differ.

| Study | Comparison | Primary RQs / hypotheses |
|-------|------------|---------------------------|
| **Study 1** | Baseline vs XAI | RQ1, H1a–H1c (understanding, cognitive load, transparency–efficiency trade-off) |
| **Study 2** | Baseline (manual navigation) vs LLM | RQ2–RQ3, H2a–H2c, H3a–H3b (trust calibration, overreliance, NL query efficiency/control) |

**Design:** Within-subjects, counterbalanced condition order, mixed methods (quantitative performance + validated scales + semi-structured exit interview).

**Session length:** 50–65 minutes (tutorial 5 min · Study 1 block ~20 min · break 5 min · Study 2 block ~20 min · surveys 10 min · interview 10–15 min).

**Sample:** Separate participant samples per study (*n* ≈ 40–50 Study 1; *n* ≈ 40–50 Study 2). Do **not** use `study=full` in production sessions — facilitator/dev only.

**URL convention:** `http://localhost:5173/?participant=P###&study=study1` (or `study2`). Add `&facilitator=1` for manipulation visibility (facilitators only).

**Condition switching:** Restart backend with `HC_EXPERIMENTAL_CONDITION=baseline|xai|llm` between blocks (or deploy three fixed URLs for multi-machine setup).

---

## 3. Session flow

| Step | Duration | Activity |
|------|----------|----------|
| 0 | 5 min | Consent, demographics pre-survey, scenario orientation |
| 1 | 5 min | **Tutorial** (neutral dashboard walkthrough on training case; no explanation logic revealed) |
| 2 | 20 min | **Study 1 block** — Condition A or B (counterbalanced): 4 timed tasks + manipulation trials |
| 3 | 3 min | Post–Study 1 condition survey (NASA-TLX, SUS subset, trust, perceived understanding) |
| 4 | 5 min | Break |
| 5 | 20 min | **Study 2 block** — remaining condition: 4 timed tasks + manipulation trials |
| 6 | 3 min | Post–Study 2 condition survey |
| 7 | 7 min | **Post-study survey** (cross-condition comparison, adoption intent, debrief items) |
| 8 | 10–15 min | Semi-structured interview |
| 9 | 2 min | Debrief (reveal intentional errors; thank/compensate) |

**Counterbalancing:** Latin square on condition order (Baseline→XAI→LLM for full crossover pilots; Study 1 uses Baseline↔XAI; Study 2 uses Baseline↔LLM). Randomize task order within block using parallel task sets (Set α / Set β) matched on difficulty.

**Facilitator script anchors:**
- “You are a care manager at a regional ACO reviewing synthetic Medicare utilization data. Risk scores are model estimates, not diagnoses.”
- “Use only what you see in the dashboard. You may take notes.”
- Do **not** mention SHAP, LLM, or intentional errors until debrief.

---

## 4. Controlled errors (revised Appendix D)

### 4.1 Primary manipulations (v2)

| ID | Error | Study | Measurement |
|----|-------|-------|-------------|
| **M2** | Incorrect **outreach recommendation** vs operational priority rule | Study 1 | Initial→final ranking; harmful switching |
| **M3** | Unsupported grounded narrative claim | Study 2 | Claim validation; evidence-link opens |
| **M4** | Incorrect NL chronic filter | Study 2 | Query reject/revise |
| **M6** | Incorrect query time window on interpretation card | Study 2 | Query reject/revise |
| **M7** | Omitted utilization threshold on interpretation card | Study 2 | Query reject/revise |

**Excluded from primary design:** inverted SHAP (M1), arbitrary wrong risk scores, confidence-framing-only trials. SHAP is **faithful** during interpretation tasks; errors target recommendations, claims, and query interpretations.

### 4.2 Sequential judgment workflow

Outreach (S1-T5) and summary validation (S2-T3) require:
1. **Initial** judgment + confidence (before AI assistance)
2. AI assistance (recommendation or frozen summary)
3. **Final** judgment + confidence + reliance source

Logged events: `task_initial_response`, `task_response`, `evidence_link_open`, `comprehension_complete`.

### 4.3 Operational priority rule

Taught in S1-T0 comprehension gate. Scoring weights: inpatient claims (×3), outpatient claims (×0.5), chronic conditions (×2), total claims (×0.1). Parallel case sets **α** and **β** reduce memory effects across conditions.

### 4.4 Facilitator-only disclosure

Manipulation assignments are hidden from participants. Use `?facilitator=1` during pilot facilitation. Debrief discloses intentional errors post-session.

---

## 5. Scenario framing (shared across tasks)

**Organization:** Fictional “Lakeview ACO Care Management.”  
**Goal:** Prioritize beneficiaries for proactive outreach based on next-year **hospitalization**, **high-utilization**, and **elevated-cost** risk.  
**Data:** CMS Synthetic RIF — demographics, FFS claims, Part D fills, chronic flags (`has_diabetes`, `has_chf`, `has_copd`, `has_ckd`, `has_hypertension`), utilization (`total_claims`, `inpatient_claims`, `readmission_30d_count`), costs (`total_payment_amt`), risk scores.

Participants should treat the dashboard as operational decision support, not bedside diagnosis.

---

## 6. Study 1 tasks — Baseline vs XAI

**Block intro (read aloud):**  
“Review the cohort and beneficiary records to identify who needs outreach and why. In the XAI version, additional explanation panels may appear; use them if helpful.”

### Task 1.1 — Cohort situational awareness (all conditions)

| Field | Detail |
|-------|--------|
| **ID** | `S1-T1` |
| **Time limit** | 4 min |
| **Goal** | Summarize population burden |
| **Instructions** | “Using the cohort overview only, answer: (a) Which age band has the highest next-year hospitalization rate? (b) Which chronic condition is most prevalent? (c) Approximate average total claims per beneficiary-year.” |
| **UI path** | Cohort overview charts + metric cards |
| **Ground truth** | From `artifacts/cohort_summary.json` for analytic year **2022** (or year specified in case packet) |
| **Metrics** | Accuracy (3 items), completion time, chart hover count (if instrumented) |

### Task 1.2 — High-risk identification (all conditions)

| Field | Detail |
|-------|--------|
| **ID** | `S1-T2` |
| **Time limit** | 5 min |
| **Goal** | Find top hospitalization-risk beneficiaries |
| **Instructions** | “Sort the risk table by hospitalization risk (descending). Select the top 5 beneficiaries and record their IDs and risk percentages.” |
| **UI path** | Risk table → sort `hospitalization_risk` |
| **XAI-only prompt** | — |
| **Metrics** | ID accuracy, rank correlation, time, `filter_change` events |

### Task 1.3 — Risk driver interpretation (XAI emphasis)

| Field | Detail |
|-------|--------|
| **ID** | `S1-T3` |
| **Time limit** | 6 min |
| **Goal** | Explain *why* a flagged beneficiary is high risk |
| **Instructions** | “Open case **B-07** (provided). What are the **top 3 drivers** of hospitalization risk? For each, state whether it increases or decreases risk and the beneficiary’s value if shown.” |
| **UI path** | Drill-down → **XAI:** local SHAP (concise top-3 default; may toggle expanded top-5) → contributor list with context previews |
| **Baseline** | Demographics + utilization + diagnosis only (no SHAP) |
| **Ground truth** | Top-3 features from `local_topk.parquet` for case B-07 |
| **Metrics** | Feature identification accuracy, direction accuracy, `explanation_view` events, disclosure toggle count |
| **Manipulation** | **M1** or **M2** when B-07 is a designated manipulation case |

### Task 1.4 — Global model literacy (XAI only; baseline gets alternate)

| Field | Detail |
|-------|--------|
| **ID** | `S1-T4a` (XAI) / `S1-T4b` (Baseline) |
| **Time limit** | 5 min |
| **XAI instructions** | “Switch the global importance view across all three risk targets. Which feature appears most important for **elevated cost** risk at the cohort level? How does that compare to hospitalization risk?” |
| **Baseline alternate** | “For case **B-12**, using only the profile panels (no explanations), list three factors *you* would weigh for hospitalization risk and why.” |
| **UI path** | **XAI:** Global importance panel + target switcher |
| **Metrics** | Correct global top feature, comparison quality (rubric 0–2), time |

### Task 1.5 — Outreach prioritization (decision task)

| Field | Detail |
|-------|--------|
| **ID** | `S1-T5` |
| **Time limit** | 6 min |
| **Goal** | Behavioral reliance / WOA |
| **Instructions** | “Cases **B-01, B-02, B-03, B-04** need outreach slots. Rank them 1–4 (1 = highest priority). Then indicate whether you primarily relied on risk scores, explanations, or your own judgment.” |
| **UI path** | Drill-down each case; XAI shows explanations |
| **Ground truth** | Rank by true `hospitalization_risk` (or composite rubric pre-specified) |
| **Metrics** | Rank distance, WOA toward model ranking, revision count |
| **Manipulation** | **M2** on one case in set |

### Task 1.6 — Explanation density comparison (XAI only; optional pilot)

| Field | Detail |
|-------|--------|
| **ID** | `S1-T6` (pilot / dissertation subsample) |
| **Time limit** | 4 min |
| **Instructions** | “For case **B-09**, view concise (top-3) then expanded (top-5) explanations. Which helped you more for an outreach decision? Rate mental effort for each.” |
| **Metrics** | Preference, NASA-TLX single-item effort delta, toggle count |

---

## 7. Study 2 tasks — Baseline navigation vs LLM

**Block intro:**  
“This dashboard may offer written summaries and a natural-language query box. Confirm queries before running them. Validate answers against the underlying data.”

### Task 2.1 — Manual cohort filtering (baseline navigation)

| Field | Detail |
|-------|--------|
| **ID** | `S2-T1` |
| **Time limit** | 5 min |
| **Goal** | Baseline for H3a efficiency comparison |
| **Instructions** | “Without using the query box, find beneficiaries with **diabetes** flagged who are in the **top 25** by hospitalization risk. How many did you identify? Note the highest-risk ID.” |
| **UI path** | Sort + scroll (no NL query in baseline; LLM arm may *also* run 2.2 for timing comparison on same goal) |
| **Metrics** | Correct count, top-ID correct, time, click count |

### Task 2.2 — Natural-language cohort query (LLM only)

| Field | Detail |
|-------|--------|
| **ID** | `S2-T2` |
| **Time limit** | 5 min |
| **Goal** | NL query efficiency & control (RQ3) |
| **Instructions** | “Use the query box: *‘Top 25 hospitalization risk with diabetes.’* Review the interpretation card, then confirm and run. Verify one result via drill-down.” |
| **UI path** | QueryPanel → interpret → confirm → results → drill-down |
| **Metrics** | `query_submit`, `query_confirm` (accepted/rejected), time, interpretation accuracy, **M4** on 25% of sessions |
| **Supported parser intents** | `list_beneficiaries` with `chronic_filter`, `sort_by`, `limit`; `cohort_summary` |

### Task 2.3 — Grounded summary interpretation (LLM only)

| Field | Detail |
|-------|--------|
| **ID** | `S2-T3` |
| **Time limit** | 6 min |
| **Goal** | RQ2 trust calibration & evidence validation |
| **Instructions** | “Open case **B-15**. Read the grounded summary and evidence links. List three claims and the source fields that support them. Flag any claim you cannot verify.” |
| **UI path** | Drill-down → GroundedSummaryPanel → evidence claim list |
| **Metrics** | Claim-source mapping accuracy, unverified-flag rate, time on summary |
| **Manipulation** | **M3** embedded summary on alternate B-15 variant |

### Task 2.4 — Cross-check summary vs record (LLM + baseline)

| Field | Detail |
|-------|--------|
| **ID** | `S2-T4` |
| **Time limit** | 5 min |
| **LLM instructions** | “The summary says utilization is a key driver. Using only utilization and diagnosis panels, is that supported? Would you change the outreach decision?” |
| **Baseline instructions** | “Using case **B-15** profile only, decide outreach yes/no and justify in one sentence.” |
| **Metrics** | Decision match to rubric, revision after cross-check |

### Task 2.5 — Comparative analytics query (LLM)

| Field | Detail |
|-------|--------|
| **ID** | `S2-T5` |
| **Time limit** | 6 min |
| **Instructions** | “Ask: *‘Cohort summary for chronic prevalence and hospitalization rate.’* After results, answer: Which chronic condition is most prevalent?” |
| **UI path** | NL query → `cohort_summary` action → grounded narrative + cohort charts |
| **Metrics** | Answer accuracy, confirm latency, fallback encountered (yes/no) |

### Task 2.6 — Control vs automation (LLM decision point)

| Field | Detail |
|-------|--------|
| **ID** | `S2-T6` |
| **Time limit** | 5 min |
| **Instructions** | “Run: *‘Top 10 elevated cost risk with heart failure.’* Before confirming, the system shows parameters. If anything looks wrong, correct by canceling and rephrasing. Proceed to outreach decision for #1.” |
| **Metrics** | Reject/confirm, reformulation count, perceived control (post-task single item) |
| **Manipulation** | **M4** wrong filter |

### Task 2.7 — Export & handoff (all conditions)

| Field | Detail |
|-------|--------|
| **ID** | `S2-T7` |
| **Time limit** | 3 min |
| **Instructions** | “Export the current risk table to CSV and generate a printable cohort summary for your supervisor.” |
| **UI path** | Export menu |
| **Metrics** | `export` event, completion |

---

## 8. Case packet preparation guide

For each `B-##` case, document in a locked answer key:

| Field | Source |
|-------|--------|
| `bene_id`, `analytic_year` | `feature_store.parquet` |
| Risk scores | `predictions.parquet` |
| Top-3 SHAP features per target | `artifacts/explanations/local_topk.parquet` |
| Chronic flags | `has_*` columns |
| Ground-truth outreach rank | Precomputed composite or single-target rule |
| Manipulation variant ID | If applicable |

**Recommended:** Select 12–16 cases spanning high/medium/low risk, varied chronic burden, stable vs unstable explanations (bootstrap stability), and equity-relevant features (age, sex, race, state, ESRD) for fairness-cue tasks.

---

## 9. Instrumentation mapping (current prototype)

| Proposal measure | Logged today? | Event / field |
|------------------|---------------|---------------|
| Session start | Yes | `session_start` |
| Sort / filter | Yes | `filter_change` |
| Drill-down | Yes | `drill_down` + `latency` |
| Explanation view | Yes | `explanation_view` |
| NL query interpret | Yes | `query_submit` |
| NL query confirm | Yes | `query_confirm` |
| Export | Yes | `export` |
| Task ID | **Partial** | API supports `task_id`; UI does not set it yet |
| Disclosure toggle | **No** | Needs `explanation_toggle` event |
| Manipulation metadata | **No** | Needs study config layer |
| Decision responses | **No** | External form or task panel |
| Dwell time on panels | **No** | Needs visibility/heartbeat events |
| Confidence framing | **No** | Not in UI |

**End of session:** Participant clicks **Export study session** (pseudonymized JSON bundle).

---

## 10. Analysis reminders (from proposal §3.6)

- Mixed-effects models: participant + task random intercepts; condition fixed effect.
- Key contrasts: Baseline vs XAI; Baseline vs LLM; accuracy × modality interaction.
- Report divergence: subjective trust vs WOA; perceived understanding vs task accuracy; convenience vs appropriate reliance.
- Qualitative: thematic analysis on interview + think-aloud (κ target > .80).

---

## 11. Ethics & debrief

- IRB: disclose **deceptive manipulations** (incorrect explanations/risks); debrief immediately post-session.
- Preregister: task scripts, case IDs, manipulation rate, analysis plan.
- Storage: pseudonymized logs only; separate key for `participant` ↔ code.

**Debrief script (abbrev):**  
“Some trials intentionally showed incorrect risk scores or explanations to study how people verify AI outputs. This was only in the research prototype with synthetic data. Your responses will help design safer dashboards.”

---

## Appendix A — Quick facilitator checklist

- [ ] Assign participant ID `P###` in URL
- [ ] Set correct `HC_EXPERIMENTAL_CONDITION` for block
- [ ] Load case packet for session set (α or β)
- [ ] Start screen recording (if consented)
- [ ] Record task times externally if task panel not built
- [ ] Administer post-condition surveys after each block
- [ ] Export session log before condition switch
- [ ] Debrief manipulations
- [ ] Backup `artifacts/logs/` and survey responses
