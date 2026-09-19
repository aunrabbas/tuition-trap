import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    return ['127.0.0.1', 'localhost'].includes(url.hostname) ? route.continue() : route.abort()
  })
})

async function chooseMajor(page: Page) {
  await page.goto('/')
  await expect(page.getByLabel('Intended major')).toBeEnabled()
  await page.getByLabel('Intended major').selectOption('1107')
}

async function calculate(page: Page, amount = '80000') {
  await chooseMajor(page)
  await page.getByLabel('Total loan amount').fill(amount)
  const response = page.waitForResponse(response => response.url().endsWith('/api/analyze'))
  await page.getByRole('button', { name: 'See your payment' }).click()
  const body = await (await response).json()
  return body
}

async function noPageOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

test('real seeded estimate, approved hierarchy, disclosure, local fonts, and chart', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const result = await calculate(page)
  const mobile = testInfo.project.name === 'mobile'
  await expect(page.getByRole('article')).toBeVisible()
  await expect(page.getByLabel('Private debt warning')).toContainText('6.52%')
  await expect(page.locator('.hero-number')).toHaveAttribute('aria-label', `${new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(result.monthly_payment)} per month`)
  await expect(page.locator('.hero-number')).toHaveCSS('font-size', mobile ? '64px' : '128px')
  await expect(page.locator('.hero-number')).toHaveCSS('font-weight', '700')
  await expect(page.locator('.take-home-percent')).toHaveText(`${(result.burden.payment_share_of_take_home * 100).toFixed(1)}%`)
  await expect(page.locator('.take-home-percent')).toHaveCSS('font-size', mobile ? '28px' : '40px')
  await expect(page.locator('.take-home-line .figure').first()).toHaveCSS('font-size', mobile ? '16px' : '18px')
  const verdict = await page.locator('.verdict').boundingBox()
  const totals = await page.locator('.repayment-totals').boundingBox()
  const chart = await page.locator('.balance-chart').boundingBox()
  expect(verdict!.y + verdict!.height).toBeLessThan(totals!.y)
  expect(totals!.y + totals!.height).toBeLessThan(chart!.y)
  const track = await page.locator('.bar-track').boundingBox()
  const boundary = await page.locator('.bar-boundary').boundingBox()
  expect(Math.abs(boundary!.x - track!.x - track!.width * Math.min(1, result.burden.payment_share_of_take_home))).toBeLessThan(1)
  await expect(page.locator('.bar-label')).toHaveText(new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(result.monthly_payment))
  await expect(page.locator('.repayment-details')).not.toHaveAttribute('open')
  await expect(page.getByText('Estimated amount disbursed to you')).not.toBeVisible()
  await expect(page.getByRole('table', { name: /Monthly repayment schedule/ })).not.toBeVisible()
  await expect(page.locator('.bar-fill')).toHaveCSS('animation-name', 'none')
  await page.evaluate(() => document.fonts.ready)
  expect(await page.evaluate(() => document.fonts.check('700 64px "Archivo Variable"'))).toBe(true)
  await noPageOverflow(page)
  await page.screenshot({ path: testInfo.outputPath('estimate.png'), fullPage: true })
  await page.getByText('Repayment details and monthly schedule', { exact: true }).click()
  await expect(page.getByText('Estimated amount disbursed to you')).toBeVisible()
  await expect(page.locator('.schedule-table tbody tr')).toHaveCount(120)
  await expect(page.locator('.schedule-table tbody tr').last().locator('td').nth(3)).toHaveText('$0.00')
  await noPageOverflow(page)
  expect(errors).toEqual([])
})

test('zero borrowing gives instructions and no zero-dollar hero', async ({ page }) => {
  await calculate(page, '0')
  await expect(page.getByRole('heading', { name: 'Start with the amount you expect to borrow.' })).toBeVisible()
  await expect(page.locator('.hero-number')).toHaveCount(0)
  await expect(page.getByText('Enter a loan amount greater than zero to estimate your payment.')).toBeVisible()
})

test('$500,000 fits the viewport and flags private debt', async ({ page }, testInfo) => {
  await calculate(page, '500000')
  await expect(page.getByLabel('Private debt warning')).toContainText('$469,000')
  await expect(page.locator('.verdict')).toContainText('dangerous', { ignoreCase: true })
  await noPageOverflow(page)
  const hero = page.locator('.hero-number')
  expect(await hero.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('large-loan.png'), fullPage: true })
})

test('school without reported earnings offers an explicit next action', async ({ page }) => {
  await page.route('**/api/schools/*/majors?*', route => route.fulfill({ json: { school_id: 215293, school_name: 'No coverage', majors: [], message: 'No programs with reported earnings are available at this school. Choose another school.' } }))
  await page.goto('/')
  await expect(page.getByText('No programs with reported earnings are available at this school. Choose another school.')).toBeVisible()
  await expect(page.getByLabel('Intended major')).toBeDisabled()
  await expect(page.getByRole('button', { name: 'See your payment' })).toBeDisabled()
})

test('zero reported income stays dangerous with an undefined share', async ({ page }) => {
  await page.route('**/api/analyze', async route => {
    const response = await route.fetch()
    const result = await response.json()
    // Controlled API edge case: arithmetic itself is covered by the Python suite.
    result.median_earnings_four_years_after_completion = 0
    result.taxes.monthly_take_home = 0
    result.burden = { ...result.burden, verdict: 'dangerous', payment_share_of_take_home: null, payment_share_of_gross_median_earnings_four_years_after_completion: null, debt_to_median_earnings_four_years_after_completion: null }
    await route.fulfill({ json: result })
  })
  await calculate(page)
  await expect(page.locator('.verdict')).toContainText('Dangerous', { ignoreCase: true })
  await expect(page.locator('.take-home-percent')).toHaveText('Unavailable')
  await expect(page.getByText('This program reports no earnings. A share of take-home pay cannot be calculated.')).toBeVisible()
  await expect(page.locator('main')).not.toContainText('NaN')
  await expect(page.locator('main')).not.toContainText('Infinity')
  await noPageOverflow(page)
})

test('school changes clear stale results and use associate data for CCAC', async ({ page }) => {
  await calculate(page)
  await page.getByRole('combobox', { name: 'School', exact: true }).selectOption('210605')
  await expect(page.getByRole('article')).toHaveCount(0)
  await expect(page.getByLabel('Intended major')).toBeEnabled()
  await expect(page.getByLabel('Intended major')).toHaveValue('')
  await expect(page.locator('#major-status')).toContainText('associate programs')
  await page.getByText('Adjust borrowing and tax assumptions', { exact: true }).click()
  await expect(page.getByLabel('Years in school', { exact: true })).toHaveValue('2')
  await page.getByLabel('Intended major').selectOption({ index: 1 })
  await page.getByRole('button', { name: 'See your payment' }).click()
  await expect(page.getByRole('article')).toBeVisible()
  await expect(page.locator('.result-context')).toContainText('Community College of Allegheny County')
})

test('API errors are actionable and retryable; keyboard focus is visible', async ({ page }) => {
  await chooseMajor(page)
  await page.route('**/api/analyze', route => route.fulfill({ status: 503, json: { detail: { message: 'School data could not be read. Restore the committed seed files and retry.' } } }))
  await page.getByRole('button', { name: 'See your payment' }).click()
  await expect(page.getByRole('alert')).toContainText('Restore the committed seed files and retry.')
  await expect(page.getByRole('button', { name: 'See your payment' })).toBeEnabled()
  await page.unroute('**/api/analyze')
  await page.getByRole('button', { name: 'See your payment' }).click()
  await expect(page.getByRole('article')).toBeVisible()
  await page.keyboard.press('Tab')
  const outline = await page.locator(':focus-visible').evaluate(element => getComputedStyle(element).outlineStyle)
  expect(outline).toBe('solid')
})

test('all three comparisons render actual API metrics and explain borrowing assumptions', async ({ page }, testInfo) => {
  const result = await calculate(page)
  if (testInfo.project.name === 'desktop') {
    await expect.poll(() => page.locator('.comparison-table').evaluate(table => table.scrollWidth <= table.parentElement!.clientWidth)).toBe(true)
  }
  const dollars = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
  for (const scenario of result.comparisons) {
    expect(scenario.status).toBe('ready')
    const row = page.locator(`[data-scenario="${scenario.kind}"]`)
    const expected = scenario.result
    await expect(row.locator('th')).toContainText(expected.school.name)
    await expect(row.locator('th')).toContainText(expected.major.title)
    await expect(row.locator('td')).toHaveText([
      dollars(expected.allocation.amount_borrowed),
      dollars(expected.median_earnings_four_years_after_completion),
      dollars(expected.taxes.monthly_take_home),
      dollars(expected.monthly_payment),
      `${(expected.burden.payment_share_of_take_home * 100).toFixed(1)}%`,
      dollars(expected.total_repaid),
      expected.burden.verdict,
    ])
  }
  await page.getByText('Comparison assumptions and borrowing by year', { exact: true }).click()
  await expect(page.locator('.comparison-method').nth(1)).toContainText('$2,916.00 / $2,916.00 / $20,000.00 / $20,000.00')
  await expect(page.locator('.comparison-method').nth(1)).toContainText('not guaranteed')
  await expect(page.locator('.comparison-method').nth(2)).toContainText('Your total borrowing is unchanged.')
  await noPageOverflow(page)
  await page.locator('.comparison-assumptions summary').click()
  await page.getByRole('heading', { name: 'Compare your paths' }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: testInfo.outputPath('comparisons.png') })
})

test('unavailable comparison explains why and does not fabricate numbers', async ({ page }) => {
  await chooseMajor(page)
  await page.getByText('Adjust borrowing and tax assumptions', { exact: true }).click()
  await page.getByLabel('Years in school', { exact: true }).fill('3')
  await page.getByRole('button', { name: 'See your payment' }).click()
  const row = page.locator('[data-scenario="community_college_transfer"]')
  await expect(row).toContainText("The two-plus-two path requires a bachelor's program with four total years in school.")
  await expect(row.locator('td')).toHaveCount(1)
  await expect(row).not.toContainText('$0')
  await noPageOverflow(page)
})
