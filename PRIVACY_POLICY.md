# Privacy Policy — TEMPLATE, NOT LEGAL ADVICE

> **Read this first:** This is a structural starting point, not a
> finished legal document. It has not been reviewed by a lawyer. Before
> using this with real users, have it reviewed by counsel familiar with
> privacy law in every jurisdiction your users are in (at minimum: GDPR
> if you have any EU users, CCPA/CPRA if you have California users, and
> your own country's requirements). Placeholders are marked `[BRACKETS]`.

Last updated: [DATE]

## 1. Who we are

[COMPANY NAME] ("AutoFlow", "we", "us") operates the AutoFlow workflow
automation platform. Contact: [PRIVACY CONTACT EMAIL].

## 2. What we collect

- **Account data**: email address, hashed password (never stored in
  plaintext — see `credentials/encryption.py`/`api/middleware/auth.py`
  for the technical implementation), MFA enrollment status.
- **Workflow data**: workflow definitions, execution history, node
  configurations you create.
- **Third-party credentials**: connection details for services you
  connect (Slack, databases, etc.) — encrypted at rest
  (`credentials/envelope.py`) and never included in data exports or
  visible to our staff in plaintext outside of the specific moment a
  workflow node you configured actually runs.
- **Usage/log data**: audit trail of actions taken in your account
  (`storage/models.py`'s `AuditLog`), IP addresses for security purposes
  (rate limiting, account lockout).

## 3. What we don't collect

- We do not sell your data.
- We do not read the contents of workflows you run against your own
  connected accounts/databases beyond what's necessary to execute them.

## 4. How we use it

- To operate the service (running your workflows, authenticating you).
- Security (rate limiting, fraud/abuse prevention, audit logging).
- [ADD: analytics, marketing, if applicable — be specific about what and why]

## 5. Your rights

- **Access**: export everything we hold about your account via
  `GET /api/privacy/export`, or the Settings page in the app.
- **Erasure**: delete your account and all associated data via
  `DELETE /api/privacy/account` (requires password confirmation), or the
  Settings page. This cascades to your workflows, credentials, and
  execution history. Security audit log entries are anonymized rather
  than deleted (your identity is removed, the record that *some* action
  occurred is retained) — this is standard practice balancing erasure
  rights against legitimate security record-keeping; [CONFIRM THIS
  BALANCE IS ACCEPTABLE IN YOUR JURISDICTION WITH COUNSEL].
- **Portability**: the export above is structured JSON, usable to move
  your data elsewhere.
- [ADD: rectification, objection, and any other rights required in your
  jurisdictions — GDPR Articles 15-22 is the relevant reference for EU users]

## 6. Data retention

- Account data: retained until you delete your account.
- Execution history: [DEFINE — this project's partitioning migration
  (`storage/migrations/versions/6a5de1399ff2_partition_executions.py`)
  makes time-based retention operationally cheap; pick and document an
  actual retention period rather than "forever"].
- Backups: [DEFINE — see `DR_RUNBOOK.md` and `k8s/29-backup-cronjob.yml`
  for current retention windows].

## 7. Third parties / sub-processors

[LIST: your cloud provider (AWS), any monitoring/analytics vendors, and
any other service that touches user data — required disclosure for
GDPR-style sub-processor lists]

## 8. International transfers

[ADDRESS IF APPLICABLE — where is data hosted, what transfer mechanism
applies if users are outside that region]

## 9. Changes to this policy

[DEFINE YOUR NOTICE PROCESS]

## 10. Contact

[PRIVACY CONTACT EMAIL / DPO IF REQUIRED]
