import { expect, test } from '@playwright/test'

test('operator can inspect comparison and safety suppression', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByText('RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED')).toBeVisible()
  await expect(page.getByText('No action')).toBeVisible()
  await expect(page.getByText('Meter north entry')).toBeVisible()

  await page.getByLabel('Failure injection').selectOption('stale')
  await expect(page.getByRole('alert')).toContainText('recommendation suppressed')
  await expect(page.getByText('No recommendation available')).toBeVisible()
  await expect(page.getByText('--:--')).toBeVisible()
})

test('advisory lifecycle stays human controlled', async ({ page }) => {
  await page.goto('/')

  await page.getByRole('button', { name: 'Acknowledge review' }).click()
  await page.getByRole('button', { name: 'Supervisor accepts advisory' }).click()
  await expect(page.getByRole('status')).toContainText('ACCEPTED')
  await page.getByRole('button', { name: 'Record human-reported physical action' }).click()
  await expect(page.getByRole('status')).toContainText('PHYSICAL ACTION CONFIRMED')
})
