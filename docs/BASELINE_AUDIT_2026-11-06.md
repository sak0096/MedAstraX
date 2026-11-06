# Current-branch audit and October finding reconciliation

## Baseline

- Baseline branch/commit: `main` at
  `925f946fc80f0b8c195e95d7c7e931b8117da46d`.
- Baseline worktree: clean.
- Working branch: `cursor/pilot-azure-foundation-beb4`.
- Repository instructions: no `AGENTS.md` was present.
- Runtime pins: Python 3.12 (`.python-version`), Node 24.16.0
  (`.nvmrc`). Audit VM: Python 3.12.3 and Node 22.23.4; container uses
  Python 3.12 and Node 24.
- Baseline verification, reproduced in a detached worktree:
  - backend: 55 passed, six warnings;
  - frontend: three tests passed;
  - frontend production build passed with a large-bundle warning.
- Baseline frontend dependency audit reported 14 vulnerabilities (five
  moderate, five high, four critical). The upgraded lockfile reports zero.
- `data/` and `artifacts/` contained no processed model/SHAP/runtime assets in
  this checkout. Model-runtime reproduction, SHAP fidelity, and container
  startup with the final asset archive therefore cannot be verified here.

The supplied context package and authority status are recorded in
`APPROVED_SOURCE_MANIFEST.md`. The actual determination was verified as dated
October 28, 2026 and valid through October 28, 2029. Exact equivalence of the
Word/PNG counterparts to the 13 reviewed PDFs remains unverified.

## October findings against baseline

| Work package | Baseline evidence | Status after this change set |
|---|---|---|
| Same-origin frontend/container | FastAPI did not mount `frontend/dist`; production CORS was localhost-only; container ran as root | SPA/static fallback added after API routes; API misses remain JSON 404; non-root image and health endpoints added |
| Canonical persistence | `instrumentation/store.py` wrote JSONL before SQLite; `language/query_cache.py` used SQLite | PostgreSQL repository/schema covers enrollment, sessions, attempts, trials, immutable responses, query versions, events, tokens, deletion ledger; local SQLite remains compatibility-only |
| Assignment/launch security | participant/study/condition came from URL and `X-Study-*`; production generated `anon-*` IDs | authenticated launch service, conservative cap transactions, TEST namespace, one-time opaque exchange, HttpOnly cookie, and server-owned binding added |
| Progression/initial lock | comprehension attempts lived in `sessionStorage`; tasks could be started directly; initial answers were append-only telemetry | attempts and lock state are durable; second failure ends tasks; initial response uniqueness and assistance gating are enforced for strict sessions. Full post-survey block progression still depends on Qualtrics callback implementation |
| Answer-key leakage/admin | `facilitator=1` returned assignments; recommendation returned `correct_ranking`, scores and manipulation flags; admin export/session/scoring routes were public | participant DTOs remove these fields; facilitator query is ignored; local admin is authenticated; production validates Entra signature, issuer, audience and required app role and fails closed without configuration |
| October task contract | catalog exposed eight tasks per study, including exploratory/export tasks; confidence was 1-7 | tutorial plus three approved tasks per study; confidence 0-100; Study 2 designation options aligned. Remaining field-level gaps are in the crosswalk |
| Query correction/lineage | Revise only reset React state; reparse could recreate the error; `_omitted_min_total_claims` was public | immutable revisions, ancestry, reject state, owner binding, direct correction fields, public-parameter stripping, zero-result clearing and deterministic tie break added |
| Frozen language/no live LLM | study mode fell back to runtime `generate_grounded_summary` when a frozen item was missing | study mode returns controlled unavailable; live provider calls reject study mode; all 12 committed summaries pass the automated evidence audit |
| Human adjudication | `human_adjudication_required: true` and all 12 queue entries pending | correctly remains a release blocker; no automated flag was relabeled as human review |
| Behavioral logging/scoring | arbitrary client telemetry could submit task/comprehension events; duplicate client task start; empty expected query set scored false | critical client event types rejected in strict mode; duplicate task start removed; canonical DB events; empty-set exact match fixed; Study 2 adoption remains explicitly unresolved |
| Qualtrics/Prolific | no authenticated integration; browser fields represented progression; no QSF | authenticated launch mock/API and field specification prepared; no actual QSF/project evidence, callback branch report, completion code or payment automation is claimed |
| Deletion/recovery | no cross-store deletion or restore ledger | coded DB deletion, revocation, cap-preserving tombstone and restore reapply command added; Qualtrics deletion remains explicitly pending/manual |
| Azure operations | deployment scaffolding only; no institutional resource evidence | parameterized templates/runbooks are supplied; no resource was provisioned and Auburn region/network/RBAC decisions remain open |

## Evidence run on this branch

- Full backend suite: 71 passed.
- Frontend: four tests passed; production build passed.
- `npm audit`: zero known vulnerabilities after dependency upgrades.
- `pip-audit` against the pinned Python lockfile: zero known vulnerabilities
  after dependency upgrades.
- PostgreSQL 16 local integration: runtime DDL refusal, explicit migration/
  verification, eight-way concurrent launch race with cap 3, unique assignment,
  token replay rejection, restart read and query-owner isolation passed.
- Frozen summary evidence audit: 12/12 passed.
- Independent adjudication gate: failed as expected; all 12 items remain
  incomplete.
- Azure Bicep compiled successfully with Bicep CLI 0.49.2; no deployment or
  institution-specific what-if was run.
- Current engineering hashes: task catalog
  `03c6948a85eb7fa04233b56932b6f1f7e56fbb7b8d5db7de62707b412e0e1d8d`;
  frozen summaries
  `337c1dfcc92b86fac4a5bae091f8f6e990cf461988d34c24452c4b8c5763f30b`;
  adjudication queue
  `d32e756a3aeb8c3a0f776442197c81a864616718a80d8b77054d5be970d50061`.
- Container build/smoke: not run because Docker is unavailable in this VM and
  final model/SHAP/data assets were not supplied in this checkout.

## First change set boundary

This is a pilot engineering foundation, not a participant release. It closes
the highest-risk local persistence, launch, leakage, confidence, task-catalog,
query-lineage, live-LLM, and frontend-serving gaps. It deliberately leaves
recruitment disabled and release-manifest verification failing until the
remaining institutional, artifact, survey, human-review, and scientific gates
are evidenced.
