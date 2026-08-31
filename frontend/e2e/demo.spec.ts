import { expect, test } from '@playwright/test'

test('room walk replay draws a drift figure', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('offline')).toBeVisible()
  await expect(page.getByText(/GPS is off|Watch the track|blue dot/i)).toBeVisible()
  await page.getByRole('button', { name: 'START' }).click()
  await expect(page.getByRole('button', { name: 'HOLD' })).toBeVisible()
  await page.getByRole('button', { name: '1×' }).click()
  await expect(page.getByRole('button', { name: 'START' })).toBeVisible({ timeout: 25_000 })
  await expect(page.getByTestId('drift')).toMatch(/[0-9]+\.[0-9]+ m/)
  await expect(page.getByTestId('drift-pct')).toContainText('% of')
  await expect(page.locator('.honesty')).toContainText('filter estimates position')
})
