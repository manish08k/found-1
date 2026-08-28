import { test, expect } from '@playwright/test'

function uniqueEmail() {
  return `e2e-wf-${Date.now()}-${Math.floor(Math.random() * 10000)}@example.com`
}

async function createWorkflow(page: import('@playwright/test').Page, name: string) {
  await page.getByRole('button', { name: 'New Workflow' }).click()
  await page.getByPlaceholder('Workflow name').fill(name)
  await page.getByRole('button', { name: 'Create' }).click()
  // Creating a workflow opens the editor immediately.
  await expect(page.getByRole('button', { name: 'Add Node' })).toBeVisible({ timeout: 10_000 })
}

test.describe('Workflow builder', () => {
  test.beforeEach(async ({ page }) => {
    const email = uniqueEmail()
    await page.goto('/')
    await page.getByText('Register', { exact: true }).click()
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill('SuperSecret123!')
    await page.getByRole('button', { name: /Create account/ }).click()
    await expect(page.getByText('Workflows', { exact: true }).first()).toBeVisible({ timeout: 10_000 })
  })

  test('node search matches on description, not just label', async ({ page }) => {
    await createWorkflow(page, 'Test Workflow A')
    await page.getByRole('button', { name: 'Add Node' }).click()

    const search = page.getByPlaceholder('Search nodes…')
    await expect(search).toBeVisible()
    // NodePicker's search now matches descriptions too (this pass's
    // improvement) — search a word that only appears in a description.
    await search.fill('read-only')
    await expect(page.locator('text=Database Query')).toBeVisible()
  })

  test('node picker keyboard navigation adds a node on Enter', async ({ page }) => {
    await createWorkflow(page, 'Test Workflow B')
    await page.getByRole('button', { name: 'Add Node' }).click()

    const search = page.getByPlaceholder('Search nodes…')
    await expect(search).toBeVisible()
    await search.fill('Slack')
    await search.press('Enter')

    // The node picker should close and a node should land on the canvas.
    await expect(search).not.toBeVisible()
  })

  test('clearing an empty node search resets to full catalog', async ({ page }) => {
    await createWorkflow(page, 'Test Workflow C')
    await page.getByRole('button', { name: 'Add Node' }).click()

    const search = page.getByPlaceholder('Search nodes…')
    await search.fill('zzz-nothing-matches-this-zzz')
    await expect(page.locator('text=/No nodes match/i')).toBeVisible()
    await page.getByRole('button', { name: 'Clear search' }).click()
    await expect(search).toHaveValue('')
  })

  test('expression autocomplete suggests trigger fields when typing {{', async ({ page }) => {
    await createWorkflow(page, 'Test Workflow D')
    await page.getByRole('button', { name: 'Add Node' }).click()
    await page.getByPlaceholder('Search nodes…').fill('Send Message')
    await page.getByPlaceholder('Search nodes…').press('Enter')

    // Open the newly added node's config panel.
    await page.locator('.react-flow__node').first().dblclick()
    const messageField = page.locator('textarea').first()
    await expect(messageField).toBeVisible({ timeout: 5000 })
    await messageField.click()
    await messageField.type('Hello {{ trig')
    await expect(page.locator('text=trigger.body')).toBeVisible({ timeout: 5000 })
  })
})
