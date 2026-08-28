# E2E Tests (Playwright)

## Status: written and fully type-checked, NOT executed

These tests were authored and validated with `npx tsc --noEmit -p
tsconfig.e2e.json` against the real Playwright and axe-core type
definitions — zero type errors. They were **not run** in the environment
they were written in, because that environment's network egress policy
explicitly blocks Playwright's browser-binary CDN:

```
Error: Download failed: server returned code 403
body 'Host not in allowlist: cdn.playwright.dev.
Add this host to your network egress settings to allow access.'
```

This is not a workaround-able limitation from inside that environment —
it's a deliberate network allowlist. Run these somewhere with normal
internet access (your own machine, a CI runner) to actually execute them.

## Running for real

```bash
cd frontend
npm install
npx playwright install chromium   # downloads the browser binary — needs real network access
npm run e2e                        # starts the Vite dev server automatically (see playwright.config.ts)
```

The backend (`main.py`) must also be running against a real Postgres +
Redis, with `scripts/seed_marketplace_templates.py` already run (the
marketplace tests assume the 8 official templates exist).

```bash
# in a separate terminal, from the repo root:
export APP_SECRET_KEY=... CREDENTIAL_ENCRYPTION_KEY=... DATABASE_URL=... REDIS_URL=...
uvicorn main:app --host 127.0.0.1 --port 8000
python -m scripts.seed_marketplace_templates
```

## What's covered

- `auth.spec.ts` — register, wrong-password error, per-account lockout after repeated failures, logout actually clearing the session. This suite specifically exists because the frontend login flow was found broken against the real backend response shapes earlier in this project (see `PRODUCTION_CHECKLIST.md`) — a regression here means someone can't log in.
- `marketplace.spec.ts` — browse, search, category narrowing, install-creates-a-real-editable-workflow, empty-state.
- `workflow-builder.spec.ts` — node picker search (including the description-matching improvement), keyboard navigation, empty-state, and the `{{ }}` expression autocomplete.
- `accessibility.spec.ts` — axe-core WCAG 2.1 A/AA scan on login/workflows/marketplace/credentials pages, plus a basic keyboard-only navigation check on the login form.

## What this does NOT cover

- Visual regression (screenshots aren't compared, just captured on failure).
- Real MFA enrollment end-to-end (would need an org + owner role set up via API first — the Python-level MFA flow is already verified live elsewhere in this project; this suite focuses on the plain login path plus the things that are UI-specific).
- Cross-browser (`playwright.config.ts` only runs Chromium — add Firefox/WebKit projects once this is running somewhere with real CI).
