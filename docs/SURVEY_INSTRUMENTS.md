# MedAstraX Post-Study Survey Instruments

**Purpose:** Capture dependent variables from dissertation §3.4 — usability, workload, trust, perceived understanding/control, and qualitative follow-up.  
**Protocol version:** 2.0  
**Administration:** External **Qualtrics** survey (not embedded in the prototype).

### Study-specific administration

| Cohort | When | Survey blocks |
|--------|------|---------------|
| **Study 1** (`study=study1`) | Once per session | Part A → (tasks) → Part B ×2 (Baseline + XAI) → Part C1 → Part D |
| **Study 2** (`study=study2`) | Once per session | Part A → (tasks) → Part B ×2 (Baseline + NL-assisted) → Part C2 → Part D |

Participants complete **one study only** — not both in the same session. Use the matching Part C block below.

**Labeling note:** The URL/API condition key remains `llm`. In Qualtrics and facilitator scripts, prefer participant-facing labels **Baseline** / **NL-assisted** (or Version A/B). Reserve “LLM” for researcher notes unless a named-model freeze + adjudication pass is complete.

**Response scales:** Unless noted, use **7-point Likert** (1 = Strongly disagree · 7 = Strongly agree).

---

## Part A — Pre-session demographics & background

*Administer before tutorial.*

| # | Item | Response type |
|---|------|---------------|
| A1 | Participant code (matches URL `?participant=`) | Text |
| A2 | Professional role | MC: Care manager / Utilization reviewer / Population health analyst / Nurse care coordinator / Physician (non-bedside) / Other: ___ |
| A3 | Primary clinical or operational domain | MC + Other |
| A4 | Years of experience in healthcare analytics or care management | MC: 2–5 / 6–10 / 11–15 / 16+ |
| A5 | How often do you use analytics dashboards or reporting tools? | 7-pt: Never → Daily |
| A6 | Prior experience with AI or ML in your work | 7-pt: None → Extensive |
| A7 | Self-rated comfort interpreting risk scores or predictive analytics | 7-pt: Very uncomfortable → Very comfortable |
| A8 | Gender (optional) | MC / Prefer not to say |
| A9 | Age range (optional) | MC |

---

## Part B — Post-condition survey (repeat after each condition block)

*Replace `[CONDITION]` with Baseline, XAI, or LLM. Approximately 5–7 minutes.*

### B1. NASA-TLX (raw subscales, 7-pt)

*“Think about the dashboard tasks you just completed in the **[CONDITION]** condition.”*

| Subscale | Left anchor (1) | Right anchor (7) |
|----------|-----------------|------------------|
| Mental demand | Low | High |
| Physical demand | Low | High |
| Temporal demand (time pressure) | Low | High |
| Performance (how well you did) | Perfect | Failure *(reverse-score for workload)* |
| Effort | Low | High |
| Frustration | Low | High |

**Analysis:** Compute Raw TLX as the unweighted mean of the six subscale ratings (Hart, 2006), matching the dissertation proposal. Do not use pairwise weights unless a later preregistration explicitly changes this.

---

### B2. System Usability Scale (SUS) — 10 items

*Standard SUS wording; 5-pt Agree/Disagree. Score 0–100 per Brooke (1996).*

1. I think that I would like to use this **[CONDITION]** dashboard frequently.
2. I found the **[CONDITION]** dashboard unnecessarily complex. *(R)*
3. I thought the **[CONDITION]** dashboard was easy to use.
4. I think I would need technical support to use this dashboard. *(R)*
5. I found the various functions in this dashboard were well integrated.
6. I thought there was too much inconsistency in this dashboard. *(R)*
7. I would imagine most people would learn to use this dashboard quickly.
8. I found the **[CONDITION]** dashboard very cumbersome to use. *(R)*
9. I felt very confident using the dashboard.
10. I needed to learn a lot before I could get going with this dashboard. *(R)*

---

### B3. Trust in automation (healthcare-adapted, 8 items)

*Adapted from Jian et al. (2000) and healthcare CDS trust literature (Tun et al., 2025; Dingel et al., 2024).*

| # | Item |
|---|------|
| T1 | The system’s risk scores are trustworthy for care-management decisions. |
| T2 | The system is reliable for identifying high-need beneficiaries. |
| T3 | I am suspicious of the system’s outputs. *(R)* |
| T4 | The system will act in my best interest as a care manager. |
| T5 | I understand why the system produced its recommendations *(in this condition)*. |
| T6 | I would use this **[CONDITION]** dashboard in my daily work if available. |
| T7 | The explanation features *(if shown)* made the system more trustworthy. |
| T8 | I could detect when the system might be wrong. |

---

### B4. Perceived understanding (4 items)

*Maps to proposal “perceived understanding” and RQ1/RQ2.*

| # | Item |
|---|------|
| U1 | I understood what drove each beneficiary’s risk scores. |
| U2 | I could explain my outreach priorities to a colleague using the dashboard. |
| U3 | The information shown was sufficient for my decisions *(in this condition)*. |
| U4 | I felt confused about how risk was calculated. *(R)* |

---

### B5. Perceived control (LLM block emphasis; ask all conditions)

| # | Item |
|---|------|
| C1 | I felt in control of how I explored the data. |
| C2 | I could verify the system’s answers against underlying data. |
| C3 | *(LLM only)* The query confirmation step helped me catch mistakes before running a query. |
| C4 | *(LLM only)* The natural-language query box made me depend on the system too much. *(R)* |
| C5 | I could have completed the same tasks without AI-generated text or explanations. |

---

### B6. Explanation modality-specific (show relevant rows only)

**XAI condition**

| # | Item |
|---|------|
| X1 | The SHAP charts helped me more than the numeric risk scores alone. |
| X2 | The amount of explanation detail was appropriate (not too much / too little). |
| X3 | Stability badges influenced how much I trusted a local explanation. |
| X4 | Fairness cues drew my attention to equity-relevant factors appropriately. |
| X5 | Expanded (top-5) explanations were worth the extra mental effort. |

**LLM condition**

| # | Item |
|---|------|
| L1 | Grounded summaries were easier to understand than raw tables. |
| L2 | Evidence links (source fields) increased my confidence in the text. |
| L3 | I would accept the summary without checking the underlying record. *(R — overreliance proxy)* |
| L4 | The system admitted uncertainty appropriately when evidence was insufficient. |
| L5 | Natural-language querying was faster than sorting and filtering manually. |

---

### B7. Single-item post-block summaries

| # | Item | Scale |
|---|------|-------|
| S1 | Overall mental workload for this block | 1–100 slider (NASA-TLX global) |
| S2 | Overall satisfaction with this dashboard version | 1–7 |
| S3 | Preferred for real outreach work: this condition vs previous *(second block only)* | MC |

---

## Part C — Post-study survey (end of session, before interview)

*Approximately 5–8 minutes. Use **C1** for Study 1 or **C2** for Study 2.*

### C1. Study 1 — Baseline vs XAI comparison

| # | Item | Response |
|---|------|----------|
| P1 | Which version helped you **understand** risk best? | MC: Baseline / XAI / No difference |
| P2 | Which version would you **use in daily work**? | MC: Baseline / XAI |
| P3 | Which version **slowed you down** the most? | MC |
| P4 | Which version made you **most likely to accept model outputs without checking**? | MC |
| P5 | Rank Baseline and XAI (1 = most preferred) for: Understanding · Speed · Trust · Control | Rank 1–2 each |

### C2. Study 2 — Baseline vs LLM comparison

| # | Item | Response |
|---|------|----------|
| P1 | Which version helped you **find and verify** cohort members best? | MC: Baseline / LLM / No difference |
| P2 | Which version would you **use in daily work**? | MC: Baseline / LLM |
| P3 | Which version **slowed you down** the most? | MC |
| P4 | Which version made you **most likely to accept generated text without checking the record**? | MC |
| P5 | Rank Baseline and LLM (1 = most preferred) for: Understanding · Speed · Trust · Control | Rank 1–2 each |

---

### C3. Behavioral reliance reflection (self-report; both studies)

| # | Item |
|---|------|
| R1 | When the dashboard and my intuition disagreed, I usually trusted the dashboard. |
| R2 | I actively looked for evidence to verify AI-generated statements. |
| R3 | Explanations made me **more** likely to follow risk scores I would have questioned otherwise. |
| R4 | I noticed at least one result that seemed inconsistent with the data. |
| R5 | If a summary sounded plausible, I rarely checked the underlying fields. *(R)* |

*R4 pairs with manipulation debrief; do not reveal manipulations before this item.*

---

### C4. Cognitive load & transparency trade-offs (H1b, H1c)

| # | Item |
|---|------|
| W1 | Visual explanations added useful transparency even when they took more time. |
| W2 | Text summaries reduced my mental effort compared with charts alone. |
| W3 | The dashboard showed **too much** AI-related information overall. *(R)* |
| W4 | I prefer concise explanations by default with the option to expand. |
| W5 | For complex cases, detailed explanations are worth the extra time. |

---

### C5. Adoption & governance (NIST AI RMF alignment)

| # | Item |
|---|------|
| G1 | I would recommend this tool to my organization only after independent validation. |
| G2 | Logging and export features would be important for auditability in production. |
| G3 | Fairness cues should be shown for demographic and equity-related predictors. |
| G4 | Query confirmation should be **required** before running NL queries in production. |
| G5 | The prototype felt safe to use because data were synthetic and clearly labeled. |

---

### C6. Open-ended (short answer)

1. What was the **most helpful** feature across all versions?
2. What was **most confusing or frustrating**?
3. Describe a moment you **trusted** the system and a moment you **doubted** it.
4. How would you change explanations or summaries for real care managers?
5. *(LLM users)* What would make the query box more trustworthy?

---

## Part D — Semi-structured exit interview (10–15 min)

*Audio-record with consent. Probe for qualitative themes in §3.4.2.*

### D1. Decision rationale
- Walk me through how you prioritized outreach in the last prioritization task.
- When did you accept vs override a risk score?

### D2. Explanation usefulness
- *(XAI)* How did you use SHAP charts vs global importance?
- *(LLM)* Did you read evidence links? When did you skip them?

### D3. Workload & workflow fit
- Did any screen feel overloaded?
- Where would this fit (or not fit) in your real workflow?

### D4. Trust calibration
- What would make you distrust the system?
- Did confidence or stability indicators change your behavior?

### D5. NL query (LLM)
- Tell me about a time you confirmed or rejected a parsed query.
- Did the confirmation step feel like friction or safety?

### D6. Manipulation debrief follow-up
- *(After reveal)* Did you notice anything incorrect? What would have helped you catch it sooner?

---

## Part E — Scoring & analysis reference

| Construct | Instrument | Primary hypothesis link |
|-----------|------------|-------------------------|
| Usability | SUS (B2) | H2a, H3b |
| Workload | NASA-TLX (B1) | H1b |
| Attitudinal trust | B3 | H2a; distinguish from reliance |
| Perceived understanding | B4 | H1a, H2a |
| Perceived control | B5 | H3b |
| Overreliance (self-report) | L3, R1, R3, R5, P4 | H2c |
| Appropriate reliance | Task WOA + M-trials | H2c, core DV |
| Task performance | Accuracy, time, rank error | H1a, H3a |
| Engagement | Logged events | §3.4.1 |

**Behavioral reliance (primary):**  
Use `scripts/score_study_session.py` on exported logs — harmful switching, appropriate rejection, etc. (see [STUDY_APPENDICES.md](./STUDY_APPENDICES.md)).

**Weight of Advice (secondary):**  
For S1-T5 outreach ranks, proportional shift from initial ranking toward AI recommendation (Panigutti et al., 2022).

**Appropriate reliance index:**  
`agreement_with_correct_AI − agreement_with_incorrect_AI` across manipulation trials.

---

## Part F — Suggested Qualtrics structure

### Study 1 survey

1. Block: Demographics (Part A)  
2. Block: Condition 1 tasks *(in MedAstraX — not in Qualtrics)*  
3. Block: Post-condition 1 (Part B; `[CONDITION]` = Baseline or XAI)  
4. Block: Condition 2 tasks  
5. Block: Post-condition 2 (Part B)  
6. Block: Post-study comparison (Part C1 or C2)  
7. Block: Reflection (Part C3–C5)  
8. Block: Open-ended (Part C6)  
9. Interview (Part D) — separate recording  

### Study 2 survey

Same structure; Part B conditions are Baseline and LLM; use Part C2 instead of C1.

*Embed `participant`, `study`, and `condition` via hidden fields set by facilitator.*
