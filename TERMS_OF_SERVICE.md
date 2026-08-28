# Terms of Service — TEMPLATE, NOT LEGAL ADVICE

> **Read this first:** This is a structural starting point, not a
> finished legal document. It has not been reviewed by a lawyer. Have it
> reviewed by counsel before using it with real users — terms of service
> carry real liability/enforceability consequences if done wrong.
> Placeholders are marked `[BRACKETS]`.

Last updated: [DATE]

## 1. Acceptance

By using AutoFlow, you agree to these terms. If you're using it on
behalf of an organization, you're agreeing on that organization's behalf
and confirming you have authority to do so.

## 2. The service

AutoFlow lets you build and run automated workflows connecting to
third-party services and databases you configure. [DESCRIBE PLAN TIERS /
LIMITS IF APPLICABLE].

## 3. Your responsibilities

- **Credentials you connect**: you're responsible for the accounts/
  databases you connect via the Credentials page, including using
  appropriately scoped access (e.g. a read-only database user for
  read-only workflows) rather than handing AutoFlow broader access than
  a workflow needs.
- **What your workflows do**: you're responsible for the actions your
  workflows take, including any `database.execute` write operations
  (gated to admin/owner roles in an organization —
  `api/middleware/rbac.py` — precisely because of this responsibility).
- **Acceptable use**: no illegal activity, no attempting to circumvent
  rate limits/security controls, no using the platform to attack third
  parties. [EXPAND — standard AUP clauses: no malware distribution, no
  scraping/abuse of connected third-party services in violation of THEIR
  terms, etc.]
- **Account security**: keep your password and MFA device secure; you're
  responsible for activity under your account. See `ONCALL.md`/
  `DR_RUNBOOK.md` for what WE do if something looks compromised on our end.

## 4. Data and privacy

Governed by `PRIVACY_POLICY.md`. Key point relevant to terms: credentials
you connect are encrypted at rest and only decrypted server-side for the
duration of an actual workflow node execution — we do not have a
"support can just look up your database password" backdoor by design.

## 5. Availability

[DEFINE SLA/UPTIME COMMITMENTS IF ANY — or explicitly state "best effort,
no SLA" if that's the actual posture. `PRODUCTION_CHECKLIST.md` and
`DR_RUNBOOK.md` describe the actual infrastructure commitments (backup
retention, RTO/RPO targets) — don't promise more in these Terms than the
infrastructure actually delivers.]

## 6. Limitation of liability

[REQUIRES LEGAL REVIEW — standard SaaS limitation-of-liability language,
tailored to your risk tolerance and insurance coverage. This is not
something to improvise without counsel, especially given `database.execute`
lets a workflow mutate a user's own connected database — think through
what "AutoFlow is not liable for data loss in YOUR database from YOUR
workflow" needs to say.]

## 7. Termination

[DEFINE: your right to suspend/terminate accounts for ToS violations,
and the user's right to delete their own account — the latter already
has a real endpoint: `DELETE /api/privacy/account`.]

## 8. Changes to these terms

[DEFINE YOUR NOTICE PROCESS]

## 9. Governing law

[DEFINE — requires legal review, depends on where your company is
incorporated and where users are located]

## 10. Contact

[LEGAL CONTACT EMAIL]
