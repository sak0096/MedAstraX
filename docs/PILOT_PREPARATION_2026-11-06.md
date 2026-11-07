# Pilot preparation implementation report

Status date: November 6, 2026  
Baseline: merged `main` commit `e2e3d4a36ed2dfa1b7c675706886b2a08d12d3b8`

## Implemented decisions

- Initial pilot enrollment is limited to three records per study. Pilot rows are
  labeled `is_pilot=true`, `recruitment_stage=initial_pilot`, and
  `confirmatory_eligible=false`. They remain in the same real-participant
  namespace and therefore continue to count against the 60-per-study and
  120-total caps. Deleted, withdrawn, failed, and incomplete enrollments are
  not recycled.
- Assignment uses a reproducible four-cell block over condition order and
  alpha/beta parallel-case order. The existing B-07/B-15 fixed cases and
  M2/M3/M4/M6/M7 catalog are validated, not replaced. The participant-derived
  error-slot function is unchanged.
- A trusted relaunch with the same opaque enrollment reference issues a new
  one-time credential for the existing enrollment. It restores the committed
  stage, block, condition, open trial, locked initial response, and all prior
  events without consuming another enrollment.
- Harmful switching and advice-consistent harmful adoption are reported
  separately, with hit counts and explicit opportunity counts. A final wrong
  answer alone is not classified as advice-consistent adoption.
- Query telemetry preserves raw total task, interpretation, revision, and
  execution durations. Scoring reports the raw arrays and simple descriptive
  means but does not impose pause, latency, outlier, or exclusion rules.
- Participant-level session listing, scoring, export, and download routes
  always require research-admin authorization, including local mode.
- The six raw TLX items, exact prompts, 1-7 anchors, and unresolved Performance
  contradiction are frozen in `study/survey_measure_contract.json`. No
  aggregate TLX value is computed.
- Study 2 baseline can proceed from its initial judgment to its final judgment
  without summary exposure or summary-specific instructions. The augmented
  condition retains the optional summary and claim checks.
- Comprehension failure, withdrawal, and technical stop close research tasks
  and return explicit `closing_questions_debrief_payment` routing metadata.
  Payment reconciliation remains independent of correctness and no unresolved
  payment amount was invented.
- In-app comprehension questions now match the supplied October Study 1 and
  Study 2 working counterparts. Result IDs, counts, and top IDs are captured
  from the current ordered result or server-owned executed query where
  available instead of requiring duplicate transcription.

## Assignment validation

`python scripts/validate_assignment_design.py --per-study 60` passed:

- Study 1 condition orders: 30 baseline-first, 30 XAI-first.
- Study 2 condition orders: 30 baseline-first, 30 language-assisted-first.
- Each study: 30 alpha-first, 30 beta-first.
- Each study: 15 records in each joint condition/case-order cell.
- Existing fixed cases: S1-T3 = B-07 and S2-T3 = B-15.
- Existing allowed manipulation IDs: M2, M3, M4, M6, M7, and `correct`.

With three initial pilot participants, exact four-cell equality is
mathematically impossible; the first three distinct cells are used. Continuing
the same sequence fills the fourth cell next.

## Checks actually run

- Backend: 74 passed, two existing pandas future warnings.
- Frontend: four passed.
- Frontend production build: passed; the existing large-bundle warning remains.
- Frozen summary evidence audit: 12/12 passed. This remains an automated audit,
  not independent human adjudication.
- Python dependency consistency: passed with no broken requirements.
- Pinned runtime loaded successfully: Python 3.12.3, NumPy 2.0.2,
  pandas 2.3.3, scikit-learn 1.6.1, XGBoost 2.1.4, SHAP 0.49.1, and
  joblib 1.5.3.
- Local same-origin smoke: `/health/live` returned 200; `/` and a dashboard
  deep link served the built SPA; an unknown `/api` path returned JSON 404.

Installing unconstrained latest libraries reproduced a useful compatibility
failure: scikit-learn 1.9 rejects the repository's `cv="prefit"` calibration
path. Reinstalling the committed lockfile restored the pinned 1.6.1 runtime and
the full suite passed. The lockfile, not unconstrained package resolution, is
therefore required for the frozen runtime.

## Frozen assets and container status

The owner confirmed that processed data, serialized models, and SHAP outputs
exist locally but are intentionally not committed. They are not present in
this cloud checkout. The expected read-only mount locations remain
`data/processed` and `artifacts`; committed study configuration and frozen
summary files remain under `study`.

Consequently, model deserialization, frozen-prediction tolerance comparison,
SHAP fidelity, and an asset-backed readiness check could not be run here.
No substitute assets were generated.

The container smoke test also remains blocked in this environment because no
Docker, Podman, Buildah, or nerdctl runtime is installed. The direct
same-origin application smoke passed, but it is not represented as a container
smoke. Run the following on the asset-bearing machine:

```text
docker compose build --no-cache medastrax
docker compose up --wait
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
python scripts/audit_frozen_summaries.py
```

Record the image digest and exact asset hashes only after that run.

## Remaining release blockers

- Mount the owner's frozen assets and run deserialization, prediction, SHAP,
  readiness, and container checks with the committed lockfile.
- Complete independent human adjudication of frozen summaries.
- Supply and branch-test the actual Qualtrics QSF, including every early ending,
  debrief, retention, and payment route.
- Resolve the comprehension-failure payment amount, retention lifecycle, and
  TLX Performance aggregate rule.
- Obtain PI approval of the existing case/error roster; this change validates
  internal consistency but does not invent or imply scientific approval.
- Complete Azure/Entra institutional configuration and sign the release
  manifest.

Recruitment remains disabled (`HC_RECRUITMENT_ENABLED=false`).
