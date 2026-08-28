# On-Call

The alert rules in `monitoring/alert-rules.yml` and the routing in
`monitoring/alertmanager.yml` are only useful if a real person is on the
other end. This is a template — fill it in before relying on paging.

## Rotation

| Week | Primary | Secondary |
|---|---|---|
| _fill in_ | _fill in_ | _fill in_ |

Recommended: weekly rotation, at least 2 people minimum so no one is
permanently on-call, secondary auto-pages if primary doesn't ack within
15 minutes (configure this escalation policy in PagerDuty/Opsgenie, not
just as a note here).

## Severity → response expectation

| Severity | Alertmanager route | Response time | Examples |
|---|---|---|---|
| `page` | PagerDuty + `#autoflow-incidents` | Ack within 15 min, any hour | 5xx rate spike, no healthy API/worker pods, DB connections near limit |
| `warn` | `#autoflow-alerts` (Slack) | Check during business hours | p99 latency elevated, DLQ growing |

## First 5 minutes of any page

1. Ack the page (stops the escalation clock).
2. Open the incident channel, post what alert fired and a link to the relevant Grafana dashboard.
3. Check `/health` and the Grafana overview dashboard — is this everyone, or one component?
4. If it's a deploy-shaped problem (alert started right after a release), consider `kubectl argo rollouts abort autoflow-api` / rollback before deep-diving root cause — restore service first, investigate after.
5. If it's data-loss-shaped, go to `DR_RUNBOOK.md` instead of improvising.

## Handoff

Whoever goes off-call at rotation boundary should leave a short note of
anything still smoldering — don't let an in-progress issue silently drop
between rotations.
