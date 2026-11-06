# October task, field, event, and scoring crosswalk

Status: engineering crosswalk from the supplied October working counterparts.
Exact equivalence to the 13 Endeavor-reviewed PDFs remains unverified.

## Shared progression

| Stage | Server record/event | Participant fields | Release rule |
|---|---|---|---|
| Qualtrics consent/background authorization | enrollment with consent version/time; one-time launch nonce | None accepted from browser as authorization | Authenticated survey service only |
| Tutorial/comprehension | `comprehension_attempts`; canonical completion event | Three answer indices | Pass 2/3; one retry; second failure ends research tasks |
| Condition block 1 | session stage, condition, case set, current task/trial | Approved task fields below | Server-owned order and task |
| Post-condition 1 | authenticated Qualtrics callback (specification pending actual project) | October shared measures | Browser parameters do not advance stage |
| Condition block 2 | same records with second assigned condition/case set | Approved task fields below | No URL-based condition switching |
| Final measures/debrief | authenticated callback plus retention choice | Comparison, optional text, retain/delete | Missing choice is not consent to retain |

Payment stage is stored independently of correctness and retention. The amount
after tutorial completion plus second comprehension failure before initial
tasks remains unresolved and must stay null/configurable.

## Study 1

Internal IDs are retained where they unambiguously correspond to an approved
task. Prototype-only S1-T1, S1-T4a, S1-T4b, and S1-T6 are removed from the
participant sequence.

| Approved task | Internal ID | Response fields | Canonical events/state | Ground truth and scores |
|---|---|---|---|---|
| Tutorial/comprehension | S1-T0 | C1-C3 answer indices | attempt number, score, pass/fail | 2/3 threshold |
| Identify high-risk members | S1-T2 | ranked IDs 1-5; confidence 0-100; optional reason | task start/response; assigned condition/case context | frozen top-five IDs; exact/order/rank accuracy |
| Interpret individual risk estimate | S1-T3 | three distinct feature/direction pairs; confidence 0-100; evidence inspected | task start/response; explanation/evidence exposure | frozen faithful SHAP feature order/direction; partial accuracy |
| Outreach prioritization | S1-T5 | initial rank 1-4 and confidence; information used; keep/revise; final rank and confidence; reason; recommendation support 1-7 | one trial; immutable initial; assistance release; final response | visible priority rule; displayed recommendation; beneficial correction, harmful switch, correct/incorrect adherence, underreliance, rank distance |

Study 1 baseline must not expose SHAP. SHAP remains faithful in the XAI
condition. The only approved controlled error is the outreach recommendation
relative to the visible priority rule.

## Study 2

Internal IDs S2-T1, S2-T3, and S2-T6 are used for both conditions. Prototype-only
S2-T2, S2-T4, S2-T5, and S2-T7 are removed from the participant sequence.

| Approved task | Internal ID | Response fields | Canonical events/state | Ground truth and scores |
|---|---|---|---|---|
| Tutorial/comprehension | S2-T0 | C1-C3 answer indices | attempt number, score, pass/fail | 2/3 threshold |
| Build target cohort | S2-T1 | returned count; top member ID; confidence 0-100; query intent/interpretation/decision/executed fields when available | filter/query lineage, confirmation/revision/rejection, execution | diabetes, year 2022, claims ≥50, top 25 hospitalization risk; exact set/count/top |
| Evaluate member record | S2-T3 | initial and final `Supported` / `Not supported` / `Insufficient information`; confidence; evidence used; keep/change; reason; per-claim `Supported by linked data` / `Not supported` / `Cannot determine` | immutable initial; optional summary release; evidence links/dwell; final | designation key and highlighted-claim key require PI review; claim accuracy and initial-to-final transition |
| Control/correct second cohort request | S2-T6 | confirm/revise/reject; final parameters; returned count/top ID; confidence; inspected elements | immutable query versions and ancestry; exact confirmed execution | CHF, year 2022, claims ≥30, top 10 elevated-cost risk; exact set/count/top/correction |

The deterministic query-error types remain condition substitution (M4), year
substitution (M6), and omitted claims threshold (M7). Public payloads must not
include manipulation IDs, omitted-parameter breadcrumbs, ground truth, or
answer keys.

## Shared questionnaires

The Qualtrics source is the October shared-measures counterpart:

- adapted six-item 1-7 Raw TLX;
- standard ten-item 1-5 SUS;
- nine 1-7 trust/understanding/calibration/control items;
- overall confidence 0-100 and satisfaction 1-7;
- condition-specific items, six comparison items, five reliance-reflection
  items, and eight optional written questions.

The TLX Performance anchors are `1 Perfect` and `7 Failure`; the accompanying
note also says to reverse-code. Raw values and anchors must be preserved.
Aggregate TLX scoring is blocked until the PI resolves that contradiction.

## Unresolved scientific mappings

The current catalog retains B-07 for Study 1 interpretation and B-15 for Study
2 record evaluation because no reviewed replacement mapping was supplied.
That is not PI approval of the parallel-case mapping. Before pilot release, the
PI must approve:

- baseline explanation-reading rubric;
- high-priority follow-up designation ground truth;
- per-condition parallel case map;
- error slot/frequency roster;
- highlighted claim keys and M3 presentation;
- whether harmful adoption is merely a transition or also requires matching
  displayed wrong advice.
