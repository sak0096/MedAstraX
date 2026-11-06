# Qualtrics integration specification

Status: implementation contract and build checklist. No QSF or Qualtrics project
export was supplied, so this document is not evidence that the survey is built
or approved.

## Trust boundary

Qualtrics calls `POST /api/integration/launch` and
`POST /api/integration/survey-callback` with the integration bearer credential.
The credential belongs in a Qualtrics server-side/web-service secret, never in
survey JavaScript, embedded data, a query string, or the app.

The app accepts no Qualtrics response ID, Prolific ID, email, consent flag,
condition, case set, or stage from the browser as authorization. Launch returns
a random, ten-minute, one-use credential. Survey JavaScript may put that
credential in the app URL only for navigation; the app removes it before
exchange and sends it in a POST body after the participant selects Continue.
The resulting opaque session is an HttpOnly, Secure, SameSite=Lax cookie.

## Embedded data

Minimum fields retained in Qualtrics:

| Field | Source | Use |
|---|---|---|
| `mx_participant_code` | launch response | pseudonymous join key and callback key |
| `mx_study` | randomizer/launch request | `study1` or `study2` |
| `mx_launch_token` | launch response | one navigation only; clear immediately after handoff |
| `mx_app_return_stage` | survey flow | expected return block, not app authorization |
| `mx_exit_reason` | branch logic | operational reconciliation |
| `mx_payment_stage` | approved payment matrix | payment independent of correctness/deletion |
| `mx_release_id` | approved release manifest | frozen release reconciliation |

Do not retain Prolific ID in the MedAstraX database or send it to the app. If
the Qualtrics project needs that identifier for payment, keep it only in the
institutionally approved survey/payment system and join there using the
pseudonymous code.

## Launch request

```json
{
  "survey_id": "approved project identifier",
  "survey_version": "approved frozen version",
  "stage": "consent",
  "consent_authorized": true,
  "study": "study1",
  "nonce": "unique server-generated callback value",
  "enrollment_reference": "optional non-identifying Qualtrics reference",
  "namespace": "pilot"
}
```

`namespace=test` is for synthetic validation and yields `TEST-###`.
Participant launch uses `pilot` and yields `P###`; it is rejected until
recruitment and all release gates are enabled. A nonce replay or cap race is a
409 and must branch to a controlled unavailable page, not create another code.

## Survey callbacks

All callbacks include the code returned at launch, the exact survey ID/version,
a fresh unique nonce, and one callback type:

| Callback | Required current app stage | Result |
|---|---|---|
| `post_condition_1_complete` | `post_condition_1_survey` | condition/block 2 tasks open |
| `final_complete` + `retention_choice=retain` | `final_survey` | retention recorded; session complete |
| `final_complete` + `retention_choice=delete` | `final_survey` | local research records removed; Qualtrics deletion ledger remains pending |
| `withdrawn` | any active stage | sessions revoked; payment reconciliation retained |
| `technical_stop` | any active stage | sessions revoked; payment reconciliation retained |

Callbacks are replay-safe by nonce. Browser redirects do not advance state.
Task completion moves the app to a survey handoff stage, and only the callback
moves it into the next block. The final retention choice is required; absence
never defaults to retain.

Example body:

```json
{
  "participant_code": "TEST-001",
  "survey_id": "SV_TEST",
  "survey_version": "october-working-counterpart",
  "callback_type": "post_condition_1_complete",
  "nonce": "unique-callback-0001"
}
```

## Flow and branch matrix

| Survey outcome | App action | Survey/payment action |
|---|---|---|
| No consent | no launch | close with approved no-consent copy; no research enrollment |
| Ineligible/background screen fail | no launch | approved screen-out/payment branch |
| Authorized and eligible | launch then app handoff | preserve pseudonymous join code |
| Tutorial pass within two attempts | condition 1 opens | continue |
| Second comprehension failure | app ends research tasks | use PI-approved amount; currently unresolved and therefore blocked |
| Condition 1 tasks complete | app returns to survey | collect condition-1 measures, then authenticated callback |
| Condition 2 tasks complete | app returns to survey | collect condition-2, comparison, reflection, debrief, retention |
| Participant withdraws | authenticated `withdrawn` callback | preserve owed-payment facts; follow approved deletion language |
| Technical failure | authenticated `technical_stop` callback | manual review; do not infer poor performance |
| Final retain | `final_complete/retain` | approved completion-code branch |
| Final delete | `final_complete/delete` | request Qualtrics-side response deletion and reconcile ledger; payment unaffected |

## Required build evidence before pilot

1. Import/export the actual QSF and record its SHA-256.
2. Record survey ID, frozen version, owner, activation state, response settings,
   anonymization settings, and retention/deletion controls.
3. Exercise every branch above with TEST codes and record expected versus
   actual app stage, Qualtrics branch, payment stage, completion code, and
   deletion status.
4. Verify no token, secret, raw response ID, Prolific ID, email, answer key, or
   condition assignment appears in URLs, browser storage, analytics, or logs.
5. Reconcile TEST enrollments, survey responses, callbacks, exits, and ledger
   entries; then purge synthetic responses according to the approved policy.

Completion codes, compensation values, the comprehension-failure amount,
actual QSF logic, and Qualtrics deletion automation remain PI/institutional
decisions. They must not be invented in configuration.
