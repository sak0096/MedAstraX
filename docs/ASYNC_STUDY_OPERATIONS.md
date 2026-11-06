# Asynchronous study operations

This runbook separates engineering tests, the covered pilot, and any later
confirmatory study. It does not authorize recruitment.

## Environments and identities

| Activity | Namespace | Codes | Data |
|---|---|---|---|
| Unit/integration/branch validation | TEST | `TEST-###` | synthetic fixtures only |
| Deployed technical validation | TEST | `TEST-###` | approved synthetic release assets |
| Covered pilot | pilot | `P001`-`P120` | only after all release gates |
| Confirmatory study | separate approved release | PI/IRB decision | requires its own frozen plan |

TEST launches never allocate a `P###` code. Pilot attempts, withdrawals,
technical stops and later deletions continue to occupy the configured cap.
No operator may edit a condition, case set, error slot, answer, score, or
completion state to balance a roster.

## Daily operational checks

Before an active recruitment window:

1. Confirm the approved release ID/image digest and manifest hashes.
2. Confirm recruitment flag, namespace, caps and Qualtrics version.
3. Check liveness, readiness, database health, backup status and callback
   errors without opening participant records.
4. Reconcile aggregate counts: launched, comprehension failure, block stages,
   completed, withdrawn, technical stop, deletion pending. Do not export
   response content for routine monitoring.
5. Resolve infrastructure incidents; scientific exclusions and payment
   disputes go to the named PI process.

## Incident actions

| Signal | Immediate action | Do not do |
|---|---|---|
| wrong image/manifest/hash | disable recruitment, preserve logs, classify affected codes | silently replace assets mid-session |
| database unavailable or schema mismatch | disable recruitment, preserve source, follow restore runbook | run runtime DDL or recreate SQLite |
| possible answer-key/assignment exposure | disable recruitment, preserve evidence, notify PI/security | delete evidence or continue recruiting |
| Qualtrics callback mismatch | stop handoffs, reconcile by pseudonymous code and nonce | advance stages from browser parameters |
| duplicate/incorrect payment | preserve owed-payment facts, use approved manual workflow | condition payment on correctness or retention |
| participant requests deletion | authenticate through approved survey process, apply local deletion, reconcile Qualtrics | free the cap slot or erase payment facts |
| technical stop | revoke session, record technical outcome, manual payment review | classify as comprehension/performance failure |

Access to individual records must be authorized, time-bound and audited.
Production admin endpoints remain unavailable until Entra validation exists.

## Pilot evidence packet

For each frozen pilot release, retain:

- approvals and decision-register closure;
- git commit, image digest, dependency and image scan results;
- release manifest and hashes;
- QSF export/hash plus complete branch report;
- task/case/error roster and independent summary adjudication;
- accessibility, browser, restart, cap-race, token-replay, deletion and restore
  evidence;
- aggregate enrollment reconciliation and incident log;
- deviations, PI disposition and go/no-go record.

Do not include secrets, direct identifiers, Prolific IDs, raw participant
responses, or participant-level answer data in the release packet.

## End of collection

Disable recruitment before the target cap or approved closing time is reached.
Reconcile survey and app stages, pending callbacks, payment stages and deletion
ledger. Export only the approved de-identified research dataset through an
authenticated, audited process. Apply the resolved retention schedule and
reapply the deletion ledger to every restore or analysis copy.
