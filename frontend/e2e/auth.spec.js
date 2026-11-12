import { expect, test } from '@playwright/test'

const email = process.env.E2E_EMAIL
const password = process.env.E2E_PASSWORD

test.describe('authentication', () => {
  test.skip(!email || !password, 'Set E2E_EMAIL and E2E_PASSWORD to run end-to-end tests')

  test('protected pages redirect to sign-in', async ({ page }) => {
    await page.goto('/app/settings/profile')
    await expect(page).toHaveURL(/\/login\?next=/)
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  })

  test('rejects wrong credentials with a generic message', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password').fill('definitely-not-the-password')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toContainText('Invalid email or password.')
  })

  test('signs in, keeps the session across reloads and signs out', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password').fill(password)
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page).toHaveURL(/\/app$/)
    await expect(page.getByText('Sales, revenue and traffic are not connected yet')).toBeVisible()

    const cookies = await page.context().cookies()
    const session = cookies.find((c) => c.name.endsWith('orbit_session'))
    expect(session?.httpOnly).toBe(true)

    await page.reload()
    await expect(page.getByText('Sales, revenue and traffic are not connected yet')).toBeVisible()

    await page.getByRole('button', { name: /sign out/i }).click()
    await expect(page).toHaveURL(/\/login/)
    await page.goto('/app')
    await expect(page).toHaveURL(/\/login\?next=/)
  })
})
