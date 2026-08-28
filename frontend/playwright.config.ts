import { defineConfig, devices } from '@playwright/test'

// Requires `npx playwright install` to fetch browser binaries (needs
// network access to Playwright's CDN — not available in every sandboxed
// build environment, including the one these tests were authored in;
// see e2e/README.md) and both the frontend dev server and the backend
// API running against a real Postgres+Redis before these can execute.
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['html'], ['github']] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: process.env.E2E_SKIP_WEBSERVER ? undefined : {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
