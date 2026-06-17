# MedAstraX Facilitator Runbook

**Audience:** Session facilitators and research assistants  
**Protocol version:** 2.0  
**Companion:** [STUDY_PROTOCOL.md](./STUDY_PROTOCOL.md)

---

## 1. Pre-session setup (30 min before)

### Environment

```bash
# .env
HC_STUDY_MODE=true
HC_LOG_EVENTS=true
HC_EXPERIMENTAL_CONDITION=baseline   # change per block
```

```bash
# Terminal 1 — backend
cd backend && source .venv/bin/activate
uvicorn hc_analytics.api.app:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Verify: cohort loads, predictions ready, explanations ready (XAI/LLM arms).

### Per participant

- [ ] Assign participant code `P###` (unique, not linked to name in logs).
- [ ] Assign **study** (`study1` or `study2`) — separate cohorts.
- [ ] Assign **condition order** (see §4 counterbalancing sheet).
- [ ] Note **case set** (α/β) — visible in session API or facilitator view.
- [ ] Open Qualtrics survey; set hidden fields: `participant`, `study`, `condition`.
- [ ] Open facilitator URL: `?participant=P###&study=study1&facilitator=1`
- [ ] Open participant URL: same without `facilitator=1` on their screen.
- [ ] Screen recording on (if consented).

---

## 2. Consent elements (IRB template — adapt to approved wording)

Cover verbally and in signed form:

1. **Purpose** — evaluating healthcare analytics interface designs for research.
2. **Voluntary** — may stop anytime without penalty.
3. **Tasks** — dashboard tasks, brief surveys, optional interview, possible screen recording.
4. **Duration** — approximately 45–55 minutes.
5. **Compensation** — as approved by IRB.
6. **Data** — synthetic Medicare-like records only; **no real patients**.
7. **Accuracy** — system outputs may be **inaccurate, incomplete, or inconsistent**; this is intentional in some trials for research validity (do **not** say which trials).
8. **Risks** — minimal: fatigue, mild frustration.
9. **Privacy** — pseudonymized logs; separate code key; retention per IRB.
10. **Contact** — PI and IRB contact information.

---

## 3. Debrief script (read after all tasks and surveys)

> Thank you for completing the session. I need to share some information we withheld earlier to preserve the validity of the study.
>
> **Some trials intentionally included incorrect AI outputs** — for example, a wrong outreach recommendation, an unsupported sentence in a summary, or a misparsed query interpretation. We did not tell you which trials because we were studying how people verify AI-assisted analytics in realistic conditions.
>
> **All beneficiary records were synthetic** CMS research data. No real patients were involved.
>
> **This was not a test of your professional competence.** We are studying interface design, not individual performance.
>
> Do you have any questions?  
> *(If IRB requires: you may request withdrawal of your data — provide procedure.)*

Do not use outdated language about “incorrect risk scores” as the primary manipulation — Study 1 errors are **wrong outreach recommendations** relative to the priority rule taught in the tutorial.

---

## 4. Counterbalancing assignment sheet

Record in secure spreadsheet (not in event logs):

| Participant | Study | Condition order | Case set | Manipulation (facilitator) | Date |
|-------------|-------|-----------------|----------|---------------------------|------|
| P001 | study1 | Baseline → XAI | α | study1=M2 | |
| P002 | study1 | XAI → Baseline | β | study1=M2 | |
| P003 | study2 | Baseline → LLM | α | study2=M4 | |

**Rules:**

- Alternate condition order across consecutive participants.
- Case set (α/β) is auto-assigned by participant ID hash — verify in facilitator panel.
- Manipulation ID is deterministic — visible only with `facilitator=1`.

---

## 5. Study 1 — session script

### Orientation (3 min)

Read scenario from STUDY_PROTOCOL §5. Open dashboard at **first condition**.

### Block A tasks

1. **S1-T0** — Ensure participant reads priority rule panel and passes comprehension (3 questions, need ≥2 correct).
2. **S1-T1 … S1-T6** — Guide through Task Panel list; only tasks matching current condition appear.
3. **S1-T5** — Confirm participant: initial rank → Show AI recommendation → final rank.
4. Do not mention manipulation assignments.

### Between conditions (5 min)

- [ ] Export session log (toolbar **Export study session**).
- [ ] Administer Qualtrics Part B for completed condition.
- [ ] Change `HC_EXPERIMENTAL_CONDITION` to second arm; participant refreshes browser.
- [ ] Repeat tasks (comprehension already passed in session).

### Close

- [ ] Qualtrics Part B (second condition) + Part C (Study 1).
- [ ] Interview Part D.
- [ ] Debrief §3.
- [ ] Final session export.
- [ ] Backup `artifacts/logs/`.

---

## 6. Study 2 — session script

### Block A — Baseline

- Condition: `HC_EXPERIMENTAL_CONDITION=baseline`
- URL: `?participant=P###&study=study2`
- Tasks: **S2-T1**, **S2-T4** (profile-only cross-check), **S2-T7** if time permits.

### Block B — LLM

- Condition: `HC_EXPERIMENTAL_CONDITION=llm`
- Tasks: **S2-T2** through **S2-T7**
- Emphasize: **read interpretation card** before confirming queries.
- **S2-T3:** initial judgment before opening summary, then drill-down B-15, then final judgment.

### Close

Same as Study 1: surveys, interview, debrief, export.

---

## 7. Troubleshooting

| Issue | Action |
|-------|--------|
| Comprehension not passing | Allow one retry; if still failing, exclude per preregistration criteria |
| Explanations missing | Run `python -m hc_analytics.explainability`; refresh |
| Frozen summary missing | Run `python scripts/generate_frozen_summaries.py` |
| Task Panel empty | Confirm `HC_STUDY_MODE=true` and `?study=study1` or `study2` |
| Participant sees manipulation labels | Remove `facilitator=1` from their URL |
| Backend wrong condition | Restart with correct `HC_EXPERIMENTAL_CONDITION` |

---

## 8. Post-session checklist

- [ ] Session exported (both condition blocks if within-subjects)
- [ ] Qualtrics responses saved with participant code
- [ ] Interview recording labeled `P###_study1_YYYY-MM-DD`
- [ ] Debrief completed
- [ ] Logs backed up
- [ ] Counterbalancing sheet updated
- [ ] Pilot notes filed (timing, comprehension pass rate, error detectability)

---

## 9. Pilot → main study gate

Do **not** begin confirmatory recruitment until:

- [ ] IRB approval obtained
- [ ] ≥3 pilot sessions per study completed
- [ ] Protocol timing fits 45–55 min
- [ ] Comprehension pass rate acceptable
- [ ] `score_study_session.py` produces sensible metrics on pilot exports
- [ ] STUDY_PROTOCOL and surveys frozen for preregistration
