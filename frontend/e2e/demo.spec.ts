import { expect, test } from '@playwright/test'

test('room walk replay draws a drift figure', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('offline')).toBeVisible()
  await expect(page.getByText('Airplane mode')).toBeVisible()
  const start = page.getByRole('button', { name: 'START' })
  await expect(start).toBeEnabled()
  await start.click()
  await expect(page.getByRole('button', { name: 'HOLD' })).toBeVisible()
  await page.getByRole('button', { name: '1×' }).click()
  await expect(page.getByRole('button', { name: 'START' })).toBeVisible({ timeout: 25_000 })
  await expect(page.getByTestId('drift')).toHaveText(/[0-9]+\.[0-9]+ m/)
  await expect(page.getByTestId('drift-pct')).toContainText('% of')
  await expect(page.locator('.honesty')).toContainText('filter estimates position')
})
