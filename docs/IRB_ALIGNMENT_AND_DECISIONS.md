# IRB alignment, readiness gates, and decision register

The October 28, 2026 exempt determination is valid through October 28, 2029
and names 13 reviewed PDFs. The supplied implementation counterparts are not
verified copies of those PDFs. This register therefore distinguishes evidence
from assumptions and leaves recruitment blocked.

## Alignment matrix

| Reviewed-area working counterpart | Engineering control/evidence | Status |
|---|---|---|
| Protocol and information letter | consent-authorized server launch; participant code; no browser assignment | counterpart implemented; exact reviewed PDF comparison pending |
| Recruitment material | pilot namespace/caps and recruitment default-off | funding, completion codes, recruitment authorization pending |
| Prescreen/background | launch occurs only after authenticated authorization | actual QSF and branch report not supplied |
| Study 1 tasks/dashboard | approved tutorial + three tasks, 0-100 confidence, sequential lock | task/case/parallel mapping PI review pending |
| Study 2 tasks/dashboard | approved tutorial + three tasks, query correction and claim choices | designation/claim ground truth PI review pending |
| Shared measures | field-level crosswalk captures TLX/SUS/trust/comparison | TLX scoring contradiction unresolved |
| Data security/data flow | PostgreSQL canonical store, one-time token, cookie binding, redaction, deletion ledger | Azure/Qualtrics deployment evidence and retention decision pending |
| Debrief/retention | explicit retain/delete callback; missing value does not retain | approved final text and Qualtrics deletion implementation pending |

Any difference in wording, task set, compensation, retention, platform/data
flow, error exposure, or recruitment must be reviewed by the PI and, where
required, submitted through the institution before release.

## Decision register

| ID | Owner | Required decision/evidence | Current state | Release effect |
|---|---|---|---|---|
| D01 | PI/IRB | Verify all 13 exact reviewed PDFs against working counterparts | not evidenced | blocks pilot |
| D02 | PI | Approve Study 1/2 parallel case map, B-07/B-15 use and error roster | unresolved | blocks pilot |
| D03 | PI/adjudicators | Independently adjudicate 12 frozen summaries and claim links | 0/12 complete | blocks pilot |
| D04 | PI/statistician | Designation and highlighted-claim keys; harmful adoption definition | unresolved | blocks scoring/release |
| D05 | PI | Resolve TLX Performance reverse-coding contradiction | unresolved; preserve raw | blocks aggregate TLX |
| D06 | PI/institution | Compensation after second comprehension failure; all branch amounts/codes | unresolved | blocks pilot |
| D07 | PI/privacy/IRB | Retention period, withdrawal and local/Qualtrics deletion timing | unresolved | blocks pilot |
| D08 | Survey owner | Supply/freeze QSF and pass complete branch/reconciliation report | not supplied | blocks pilot |
| D09 | Auburn IT/security | Azure subscription, region, network, ingress, RBAC, monitoring and recovery | not approved/evidenced | blocks deployment |
| D10 | Identity owner | Entra registration, audience and admin app-role assignment | JWT signature/issuer/audience/role validation implemented; tenant configuration not evidenced | blocks production research admin validation |
| D11 | Data/model owner | Supply immutable processed data, models, SHAP and manifest | absent in checkout | blocks fidelity/container validation |
| D12 | PI/security | Approve public sharing/de-identification and export policy | unresolved | blocks publication/export |
| D13 | PI/methods | Final power analysis, exclusion plan and preregistration | not evidenced | blocks confirmatory readiness |
| D14 | Release owner | Sign release manifest after image, assets, survey and tests freeze | template only | blocks pilot |

## Readiness gates

### Internal technical validation

Allowed now only with synthetic TEST data and no external recruitment.
Remaining requirements for a deployed TEST validation include Bicep
institutional choices, Entra or disabled admin workflows, final assets,
container/image scan, database migration-role test, restore drill and QSF test
project. Internal validation is not a pilot.

### Covered pilot

Requires D01-D12, a signed immutable release manifest, independent security and
accessibility review, complete Qualtrics branch test, PostgreSQL concurrency
and restart evidence, Azure backup/restore evidence, container smoke, and PI/
institutional go/no-go. Every pilot participant counts toward caps.

### Confirmatory readiness

Requires a completed and reviewed pilot, disposition of every deviation,
frozen outcome/scoring/exclusion plan, D13, final power analysis,
preregistration where intended, and any required IRB modification. The current
prototype is not confirmatory-ready.

## Current go/no-go

- Local engineering foundation: conditional go for further synthetic work.
- Azure technical deployment: no-go until institutional parameters and assets.
- Covered pilot recruitment: no-go.
- Confirmatory recruitment/analysis: no-go.
