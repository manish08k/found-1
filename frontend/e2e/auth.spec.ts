import { test, expect } from '@playwright/test'

/**
 * These specifically re-test the exact gap found earlier in this
 * project: the frontend login flow silently breaking against the
 * backend's real response shapes (access_token vs mfa_code_required vs
 * mfa_enrollment_required). A regression here means someone can't log in
 * — this suite exists so that never ships unnoticed again.
 */

function uniqueEmail() {
  return `e2e-${Date.now()}-${Math.floor(Math.random() * 10000)}@example.com`
}

test.describe('Auth', () => {
  test('a new user can register and lands on the workflows page', async ({ page }) => {
    const email = uniqueEmail()
    await page.goto('/')

    await page.getByText('Register', { exact: true }).click()
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill('SuperSecret123!')
    await page.getByRole('button', { name: /Create account/ }).click()

    // No MFA required for a fresh solo account -> straight into the app.
    await expect(page.getByText('Workflows', { exact: true }).first()).toBeVisible({ timeout: 10_000 })
  })

  test('wrong password shows an error and does not log in', async ({ page }) => {
    const email = uniqueEmail()
    await page.goto('/')

    // Register first so the account exists.
    await page.getByText('Register', { exact: true }).click()
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill('SuperSecret123!')
    await page.getByRole('button', { name: /Create account/ }).click()
    await expect(page.getByText('Workflows', { exact: true }).first()).toBeVisible({ timeout: 10_000 })

    // Log out, then try the wrong password.
    await page.getByTitle('Logout').click()
    await expect(page.getByPlaceholder('you@example.com')).toBeVisible()
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill('WrongPassword!')
    await page.getByRole('button', { name: /Sign in/ }).click()

    await expect(page.locator('text=/invalid credentials/i')).toBeVisible({ timeout: 5000 })
  })

  test('repeated failed logins lock the account (per-account lockout)', async ({ page, request }) => {
    const email = uniqueEmail()
    // Register via API directly — this test is about the lockout
    // response, not re-testing the registration UI again.
    await request.post('http://localhost:8000/api/auth/register', {
      data: { email, password: 'SuperSecret123!' },
    })

    await page.goto('/')
    for (let i = 0; i < 6; i++) {
      await page.getByPlaceholder('you@example.com').fill(email)
      await page.getByPlaceholder('••••••••').fill('WrongPassword!')
      await page.getByRole('button', { name: /Sign in/ }).click()
      await page.waitForTimeout(300)
    }
    await expect(page.locator('text=/locked/i')).toBeVisible({ timeout: 5000 })
  })

  test('logout actually clears the session (protected page redirects to login)', async ({ page }) => {
    const email = uniqueEmail()
    await page.goto('/')
    await page.getByText('Register', { exact: true }).click()
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill('SuperSecret123!')
    await page.getByRole('button', { name: /Create account/ }).click()
    await expect(page.getByText('Workflows', { exact: true }).first()).toBeVisible({ timeout: 10_000 })

    await page.getByTitle('Logout').click()
    await expect(page.getByPlaceholder('you@example.com')).toBeVisible()

    await page.reload()
    await expect(page.getByPlaceholder('you@example.com')).toBeVisible()
  })
})
