# Azure deployment and recovery runbook

Status: parameterized design only. No Azure resource, subscription approval,
region decision, DNS name, certificate, service principal, secret, or budget
was provisioned or verified.

## Architecture

`infra/azure/main.bicep` defines:

- a Linux App Service plan and single same-origin container app;
- Premium Azure Container Registry with managed-identity image pull;
- PostgreSQL Flexible Server 16 with private delegated subnet and private DNS;
- private Blob Storage for immutable/versioned release artifacts;
- Key Vault with RBAC, purge protection and private access;
- VNet integration, private endpoints/DNS for ACR, Blob and Key Vault;
- Log Analytics, Application Insights, health probe, and budget alerts.

The participant web app remains HTTPS-public because remote participants must
reach it. Data services and registry are private. Production OpenAPI/docs are
disabled. The application identity receives only ACR pull, Key Vault secret
read, and Blob data contributor roles. Database runtime and migration roles are
separate credentials even though role creation is an operator step.

## Decisions required before validation

Owner: PI/Auburn IT unless reassigned in the decision register.

1. Approved subscription, resource group, region, naming/tags, public hostname
   and any WAF/Front Door requirement.
2. VNet address ranges, DNS ownership, outbound egress rules, private endpoint
   policy and whether institutional access must traverse private connectivity.
3. Entra tenant/app registrations, administrators, break-glass process,
   deployment identity and least-privilege role assignments.
4. PostgreSQL HA/backup retention, point-in-time restore target, maintenance
   window, log retention and alert destinations.
5. Cost center, monthly threshold and contacts.
6. Approved retention period and deletion workflow.

## Deployment sequence

Commands below are operator instructions, not commands run by this change set.

1. Obtain approvals above and create a protected bootstrap vault. Generate
   separate random session and integration secrets. Never pass secrets on a
   command line, save them in git, or put them in a build log.
2. Copy `pilot.parameters.example.json` outside the repository, replace every
   `REQUIRES_*` marker, and keep `recruitmentEnabled=false`,
   `enrollmentNamespace=test`.
3. Run Bicep validation and a what-if under the deployment identity. Security
   and IT review the complete diff before deployment.
4. Deploy infrastructure. Create PostgreSQL roles:
   - migration role: DDL only during a controlled release;
   - runtime role: connect and CRUD on application tables, no schema ownership;
   - read-only research role: approved views only, time-bound access.
5. With the migration role, run
   `python -m hc_analytics.persistence migrate`. Revoke/disable migration
   credentials before starting the app.
6. Build the image from a clean commit, scan it, push by immutable digest, and
   fill the release manifest with image digest plus exact approved data/model,
   SHAP, task catalog, frozen summary and survey hashes.
7. Start one deployment slot using TEST namespace. Verify Key Vault references,
   `/health/live`, `/health/ready`, database schema, private dependency
   resolution and app logs. Readiness may be operationally healthy while
   correctly reporting participant launch blocked.
8. Run the complete Qualtrics branch matrix with TEST codes, accessibility
   review, cross-browser checks, cap-race test, restart test, backup/restore
   exercise, deletion/reapply exercise and independent adjudication.
9. Record immutable evidence and approvals in the release manifest. Only then
   set approved policy/payment values, `enrollmentNamespace=pilot`, and
   `recruitmentEnabled=true` in a separately reviewed release.

## Alerts

Configure action groups for:

- `/health/live` failure and repeated restarts;
- `/health/ready` infrastructure failure;
- HTTP 5xx, callback 401/409 spikes, launch 409 cap events;
- database CPU/storage/connections/replica or backup failure;
- Key Vault denial, secret expiry and unexpected access;
- deletion ledger pending age;
- actual and forecast budget thresholds.

Participant codes and request/response bodies must not be telemetry dimensions.
The application does not need live LLM egress during either study.

## Backup and restore drill

1. Stop launch by setting recruitment false; do not delete the source server.
2. Record source server, database, release ID, restore point and operator.
3. Restore Flexible Server to an isolated name/network.
4. Run schema verification with the runtime code; do not run migrations merely
   to make a stale restore appear healthy.
5. Reapply the deletion ledger before any analysis or service use.
6. Reconcile enrollment counts, callbacks, task/response counts, query lineage
   and pending Qualtrics deletions. Confirm deleted research payloads remain
   absent and still consume their enrollment slots.
7. Run TEST smoke cases, archive the drill evidence, and destroy the isolated
   restore according to policy.

## Rollback

Rollback is an immutable image/config switch, not an in-place code edit.
Disable recruitment first. If the schema is backward-compatible, route to the
prior verified image digest and manifest. If not, restore to a new server at
the documented pre-release point, reapply deletion records, verify counts, and
then switch the database secret. Never downgrade over the only database copy.

## Current blockers

- Azure approval and all institution-specific decisions above;
- final asset archive and runtime fidelity evidence;
- actual QSF and callback branch report;
- approved Entra app registration, audience, app-role assignment and live validation;
- human adjudication of all frozen summaries;
- approved retention/payment decisions and release manifest;
- tested container image and Azure backup/restore evidence.
