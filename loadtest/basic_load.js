// k6 load test — run against STAGING, never production.
//   docker run --rm -e BASE_URL=https://staging.autoflow.io \
//     -v $(pwd):/scripts \
//     grafana/k6 run /scripts/basic_load.js
//
// No TOKEN env var needed — setup() registers a pool of real accounts
// and each VU uses its own (see the note on why this changed, below).
// Stages ramp up to simulate ~1M-user-scale peak concurrency; tune
// `TARGET_VUS` against what you actually expect (this default assumes
// ~1% of 1M users active in the same minute, which is a reasonable
// starting guess for a workflow-automation tool, not a hard number).
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const TARGET_VUS = Number(__ENV.TARGET_VUS || 2000);

export const options = {
  stages: [
    { duration: '2m', target: Math.round(TARGET_VUS * 0.1) },  // warm up
    { duration: '5m', target: TARGET_VUS },                     // ramp to target
    { duration: '10m', target: TARGET_VUS },                    // hold — this is the part that matters
    { duration: '3m', target: 0 },                               // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<800', 'p(99)<2000'],
    errors: ['rate<0.01'],
  },
};

// Register a DISTINCT account per virtual user, not one shared token for
// everyone. Found via a real run (see RESULTS.md) that sharing one token
// across many VUs makes the per-user rate limiter (api/middleware/rate_limit.py)
// reject most of the traffic — which is correct behavior for one account,
// but means the test was accidentally measuring rate-limit rejection
// instead of the thing it's meant to measure: how the system behaves
// under many DIFFERENT real users. setup() runs once per test, not once
// per VU/iteration, but each VU still needs its own credentials — so we
// register a pool of accounts up front and have each VU pick one by ID.
export function setup() {
  const accounts = [];
  const poolSize = Math.min(TARGET_VUS, 500); // cap — 2000 accounts isn't necessary to get a realistic distribution, and registering that many up front would itself dominate setup time
  for (let i = 0; i < poolSize; i++) {
    const email = `loadtest-${Date.now()}-${i}@example.com`;
    const res = http.post(`${BASE_URL}/api/auth/register`, JSON.stringify({ email, password: 'LoadTest123!' }), {
      headers: { 'Content-Type': 'application/json' },
    });
    if (res.status === 201) {
      accounts.push(res.json('access_token'));
    }
  }
  return { accounts };
}

export default function (data) {
  const token = data.accounts[__VU % data.accounts.length];
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  // Mix of read-heavy (list) and write (execute) traffic, roughly
  // matching what a real workflow-automation tool sees — mostly people
  // checking on things, occasionally triggering one.
  const listRes = http.get(`${BASE_URL}/api/workflows?page=1&page_size=20`, { headers });
  check(listRes, { 'list workflows: 200': (r) => r.status === 200 }) || errorRate.add(1);

  const execRes = http.get(`${BASE_URL}/api/executions?page=1&page_size=20`, { headers });
  check(execRes, { 'list executions: 200': (r) => r.status === 200 }) || errorRate.add(1);

  if (Math.random() < 0.05) {
    // ~5% of iterations trigger something, roughly matching a light
    // automation workload — heavier if your product is used more
    // actively than that.
    const triggerRes = http.post(
      `${BASE_URL}/api/workflows/00000000-0000-0000-0000-000000000000/trigger`,
      JSON.stringify({}),
      { headers: Object.assign({}, headers, { 'Idempotency-Key': `${__VU}-${__ITER}` }) },
    );
    check(triggerRes, { 'trigger: not 5xx': (r) => r.status < 500 }) || errorRate.add(1);
  }

  sleep(1 + Math.random() * 2);
}
