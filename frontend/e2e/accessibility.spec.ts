import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

function uniqueEmail() {
  return `e2e-a11y-${Date.now()}-${Math.floor(Math.random() * 10000)}@example.com`
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

/**
 * Scans for WCAG 2.1 A/AA violations. This is a floor, not a ceiling —
 * axe catches missing labels/roles/contrast issues but not things like
 * "is this actually usable with a screen reader end-to-end" or keyboard-
 * only navigation through the canvas. Treat a clean run here as "no
 * obvious automated-detectable issues", not "fully accessible".
 */
test.describe('Accessibility (axe-core, WCAG 2.1 A/AA)', () => {
  test('login page has no critical/serious violations', async ({ page }) => {
    await page.goto('/')
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()
    const serious = results.violations.filter(v => v.impact === 'critical' || v.impact === 'serious')
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([])
  })

  test('workflows list page has no critical/serious violations', async ({ page }) => {
    await registerAndLogin(page)
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()
    const serious = results.violations.filter(v => v.impact === 'critical' || v.impact === 'serious')
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([])
  })

  test('marketplace page has no critical/serious violations', async ({ page }) => {
    await registerAndLogin(page)
    await page.getByText('Marketplace', { exact: true }).click()
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()
    const serious = results.violations.filter(v => v.impact === 'critical' || v.impact === 'serious')
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([])
  })

  test('credentials page has no critical/serious violations', async ({ page }) => {
    await registerAndLogin(page)
    await page.getByText('Credentials', { exact: true }).click()
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()
    const serious = results.violations.filter(v => v.impact === 'critical' || v.impact === 'serious')
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([])
  })

  test('keyboard-only: can tab through the login form and submit', async ({ page }) => {
    await page.goto('/')
    await page.keyboard.press('Tab') // Google button
    await page.keyboard.press('Tab') // email
    await page.keyboard.type('keyboardtest@example.com')
    await page.keyboard.press('Tab') // password
    await page.keyboard.type('SuperSecret123!')
    // Should be able to reach and activate submit without a mouse.
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: /Sign in/ })).toBeFocused()
  })
})
