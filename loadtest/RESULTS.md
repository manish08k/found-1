# Load Test Results

## What this is — and isn't

This is a **real k6 run against a real, live backend** (Postgres + Redis +
uvicorn, all actually running), not a simulated or hypothetical result.
It is **not** a real production-capacity benchmark — it ran on a single
sandboxed box with a stock local Postgres (`max_connections=100`, no
PgBouncer, no tuning), not the target k8s deployment in `k8s/`. Treat the
*failure mode found* as real and worth acting on; treat the specific
numbers (req/s, VU counts) as not representative of real infra capacity.

## Run 1: 20 VUs, 30s, realistic traffic shape

```
k6 run --vus 20 --duration 30s loadtest/basic_load.js
```

- 2,919 requests, 95.7 req/s
- **58.9% failed** — investigated below
- p95 latency on successful requests: 208ms

Initial hypothesis (wrong, corrected below): assumed this was the new
per-user rate limiter (`api/middleware/rate_limit.py`) correctly rejecting
unrealistic traffic — all 20 virtual users shared a single auth token
because the test script only registers one account, so from the
backend's perspective this looked like one real user firing ~96 req/s
sustained, comfortably over the 600/min per-user limit. That explains
*part* of the failures (429s), but not all of them, so it was worth
digging further rather than stopping at a plausible-sounding first guess.

## Run 2: isolating the real failure — 900 concurrent requests, one token

```python
await asyncio.gather(*[one_req(client) for _ in range(900)])
```

**Result: 358 succeeded (200), 300 rate-limited (429, expected/correct),
182 real server errors (500), 60 client-side read timeouts.**

The 500s are the actual finding:

```
asyncpg.exceptions.TooManyConnectionsError: sorry, too many clients already
```

**Root cause, confirmed with real numbers**: this sandbox's Postgres has
`max_connections = 100` (verified via `SHOW max_connections`). The app's
`DATABASE_POOL_SIZE=20` + `DATABASE_MAX_OVERFLOW=40` allows up to 60
connections **per uvicorn worker process**; this test ran with
`--workers 2`, so up to 120 possible connections — already over the
database's limit before accounting for anything else connected to it.

## Why this matters beyond this one sandbox

This is the exact failure mode `PRODUCTION_CHECKLIST.md` flagged from the
very first infrastructure review of this project — "no connection pooler,
you'll exhaust Postgres connections fast" — and `k8s/25-pgbouncer.yml`
was built specifically to prevent it. This load test run is now direct,
reproducible **evidence** that the failure mode is real and easy to
trigger, not just a theoretical concern from reading the architecture.

It also means: **do not skip deploying PgBouncer before real traffic**,
even at moderate scale. 900 concurrent requests against one endpoint is a
plausible burst (a popular workflow's webhook firing, a dashboard
refresh storm after an outage, etc.) — not an extreme adversarial number.

## What to do with this

1. Confirmed, not just assumed: PgBouncer (`k8s/25-pgbouncer.yml`) needs
   to be deployed before opening this up to real traffic, not treated as
   a "nice to have, add it later" item.
2. Re-run this same test against a staging deployment that DOES have
   PgBouncer in front, to confirm the fix actually resolves it — that
   hasn't been done yet (this sandbox doesn't have a k8s cluster to
   deploy PgBouncer into).
3. Consider whether `DATABASE_POOL_SIZE`/`DATABASE_MAX_OVERFLOW` defaults
   are sized correctly relative to your real Postgres `max_connections`
   and expected pod replica count — `(pool_size + max_overflow) × max
   replicas` should stay comfortably under the database's connection
   limit even without PgBouncer as a backstop.
4. The 60 client-side read timeouts under sustained connection exhaustion
   suggest requests were queueing rather than failing fast — worth adding
   an explicit statement/pool-checkout timeout so a connection-starved
   period degrades as fast 503s instead of slow hangs.

## Not yet done

- Running this against the actual `k8s/` deployment with PgBouncer, KEDA
  autoscaling, and a managed RDS instance — needs real cloud infra
  (`infra/terraform/aws/`), which hasn't been applied anywhere.
- A realistic multi-user load pattern (this run's "Run 1" used one shared
  token across 20 VUs, which isn't how real traffic looks — real load
  testing should register/use many distinct accounts, matching how 1M
  actual users would hit the per-user rate limiter independently rather
  than all sharing one bucket).
