import { test, expect } from '@playwright/test'

function uniqueEmail() {
  return `e2e-market-${Date.now()}-${Math.floor(Math.random() * 10000)}@example.com`
}

async function registerAndLogin(page: import('@playwright/test').Page) {
  const email = uniqueEmail()
  await page.goto('/')
  await page.getByText('Register', { exact: true }).click()
  await page.getByPlaceholder('you@example.com').fill(email)
  await page.getByPlaceholder('••••••••').fill('SuperSecret123!')
  await page.getByRole('button', { name: /Create account/ }).click()
  await expect(page.getByText('Workflows', { exact: true }).first()).toBeVisible({ timeout: 10_000 })
}

test.describe('Marketplace', () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page)
  })

  test('browsing shows seeded templates', async ({ page }) => {
    await page.getByText('Marketplace', { exact: true }).click()
    // scripts/seed_marketplace_templates.py must have been run against
    // this environment's database for this to find anything.
    await expect(page.locator('text=Slack Notification on Webhook')).toBeVisible({ timeout: 10_000 })
  })

  test('search narrows results', async ({ page }) => {
    await page.getByText('Marketplace', { exact: true }).click()
    await page.getByPlaceholder('Search templates…').fill('slack')
    await expect(page.locator('text=Slack Notification on Webhook')).toBeVisible()
    await expect(page.locator('text=WhatsApp Order Confirmation')).not.toBeVisible()
  })

  test('installing a template creates an editable workflow and opens it', async ({ page }) => {
    await page.getByText('Marketplace', { exact: true }).click()
    await page.locator('text=Daily Database Report to Slack').click()
    await page.getByRole('button', { name: /Install to my workspace/ }).click()

    await expect(page.locator('text=/Installed/')).toBeVisible({ timeout: 10_000 })
    // Should land back in the workflow editor with the installed
    // workflow's nodes visible on the canvas.
    await expect(page.locator('text=Every Weekday 9am')).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('text=Count New Signups')).toBeVisible()
    await expect(page.locator('text=Post Report')).toBeVisible()
  })

  test('empty search shows a clear-filters empty state', async ({ page }) => {
    await page.getByText('Marketplace', { exact: true }).click()
    await page.getByPlaceholder('Search templates…').fill('this-will-never-match-anything-xyz')
    await expect(page.locator('text=/No templates match/i')).toBeVisible()
    await page.getByRole('button', { name: /Clear filters/ }).click()
    await expect(page.locator('text=Slack Notification on Webhook')).toBeVisible()
  })
})
