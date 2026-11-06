// M1 end-to-end: a new learner browses, filters, wishlists, buys with a coupon (Stripe
// simulated by the harness), gets a refund, enrols in a free course and starts a trial.
const { chromium, devices } = require('playwright')
const assert = require('assert')
const OUT = process.argv[2] || 'shots'
require('fs').mkdirSync(OUT, { recursive: true })
const { BASE, py: run, lastLine, NEW_USER_PASSWORD } = require('./lib')
const stripe = (kind, id) => run('e2e_stripe.py', kind, id)

;(async () => {
  const b = await chromium.launch()
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } })
  const p = await ctx.newPage()
  const problems = []
  p.on('pageerror', (e) => problems.push('pageerror: ' + e.message))
  p.on('console', (m) => m.type() === 'error' && !/status of 401/.test(m.text()) && problems.push('console: ' + m.text()))
  p.on('response', (r) => r.url().includes('/api/') && r.status() >= 500 && problems.push(`HTTP ${r.status()} ${r.url()}`))
  const step = (s) => console.log('✓', s)
  const shot = (n) => p.screenshot({ path: `${OUT}/${n}.png` })

  const email = lastLine(run('e2e_user.py', NEW_USER_PASSWORD))
  console.log('  new learner:', email)
  await p.goto(BASE + '/login')
  await p.getByLabel('Email').fill(email)
  await p.getByLabel('Password').fill(NEW_USER_PASSWORD)
  await p.getByRole('button', { name: 'Log in' }).click()
  await p.waitForURL(/\/learn$/)
  step('signed in')

  // catalogue: total, filters, chips, list view
  await p.goto(BASE + '/courses', { waitUntil: 'networkidle' })
  const total = await p.getByText(/^\d+ courses?$/).first().textContent()
  await p.getByRole('radio', { name: 'Development' }).first().click()
  await p.getByRole('button', { name: /Remove filter Development/ }).waitFor()
  await p.waitForTimeout(700)
  assert(await p.getByRole('button', { name: /Remove filter Development/ }).isVisible(), 'chip shown')
  const devTotal = await p.getByText(/^\d+ courses?$/).first().textContent()
  assert.notStrictEqual(devTotal, total, 'category filter changes the total')
  await p.getByRole('button', { name: 'list view' }).click()
  await p.waitForTimeout(500)
  await shot('m1-01-catalogue-filtered-list')
  await p.getByRole('button', { name: /Remove filter Development/ }).click()
  await p.getByRole('button', { name: 'grid view' }).click()
  await p.getByRole('radio', { name: 'Paid' }).click()
  await p.getByRole('button', { name: /Remove filter Paid/ }).waitFor()
  await p.waitForTimeout(600)
  await shot('m1-02-catalogue-grid')
  step(`catalogue filters work (${total} → ${devTotal})`)

  // course page: add to cart (badge), wishlist a second one, then cart it too
  const cards = p.locator('main a[href^="/courses/"]')
  const firstHref = await cards.nth(0).getAttribute('href')
  const secondHref = await cards.nth(1).getAttribute('href')
  await cards.nth(0).click()
  await p.waitForSelector('#curriculum')
  await p.getByRole('button', { name: 'Add to cart' }).click()
  await p.getByText('Added to your cart').waitFor()
  await p.getByRole('link', { name: /Cart, 1 course/ }).waitFor()
  await shot('m1-03-course-added')
  step(`added ${firstHref} to the cart; badge shows 1`)
  await p.goto(BASE + secondHref)
  await p.getByRole('button', { name: 'Save to wishlist' }).click()
  await p.getByText('Saved to your wishlist').waitFor()
  await p.goto(BASE + '/wishlist')
  await p.getByRole('button', { name: 'Add to cart' }).first().click()
  await p.getByText('Moved to your cart').waitFor()
  await p.getByRole('link', { name: /Cart, 2 courses/ }).waitFor()
  step('wishlist → cart works; badge shows 2')

  // cart: bad coupon, good coupon, checkout
  await p.goto(BASE + '/cart', { waitUntil: 'networkidle' })
  assert.strictEqual(await p.locator('main li').count(), 2, 'two lines in cart')
  const before = await p.locator('aside p.text-4xl').textContent()
  await p.getByLabel('Coupon code').fill('NOPE')
  await p.getByRole('button', { name: 'Apply' }).click()
  await p.getByRole('alert').filter({ hasText: /not valid/ }).waitFor()
  await p.getByLabel('Coupon code').fill('WELCOME20')
  await p.getByRole('button', { name: 'Apply' }).click()
  await p.getByText('WELCOME20 applied').waitFor()
  const after = await p.locator('aside p.text-4xl').textContent()
  assert.notStrictEqual(after, before, 'coupon lowers the total')
  await shot('m1-04-cart-coupon')
  step(`coupon: ${before} → ${after}`)
  await p.getByRole('button', { name: /Checkout/ }).click()
  await p.waitForURL(/checkout\/success\?order=/)
  await p.getByText('Confirming your payment').waitFor()
  const orderId = new URL(p.url()).searchParams.get('order')
  console.log('  webhook:', stripe('order', orderId))
  await p.getByText('Payment complete').waitFor({ timeout: 15000 })
  await shot('m1-05-success')
  await p.getByRole('link', { name: /Cart$/ }).waitFor()
  step('checkout → webhook → order paid; cart emptied')

  // the course page now says enrolled
  await p.goto(BASE + firstHref)
  await p.getByText("You're enrolled").waitFor()
  step('course page shows enrolled')

  // refund one item
  await p.goto(BASE + '/account/orders', { waitUntil: 'networkidle' })
  await p.getByRole('button', { name: 'Refund' }).first().click()
  await p.getByRole('dialog').getByRole('button', { name: 'Refund' }).click()
  await p.getByText('Refund issued').waitFor()
  await p.getByText('Partly refunded').waitFor()
  await shot('m1-06-orders-refunded')
  step('refund issued; order shows partly refunded')

  // free course
  await p.goto(BASE + '/courses?price=free', { waitUntil: 'networkidle' })
  const freeLink = p.locator('main a[href^="/courses/"]').first()
  if (await freeLink.count()) {
    await freeLink.click()
    await p.getByRole('button', { name: 'Enrol for free' }).click()
    await p.waitForURL(/\/learn\/[^/]+\/lecture\//) // free: straight into the player (M2)
    await p.getByText("You're enrolled").first().waitFor()
    step('free course: enrolled without payment, opened in the player')
  } else step('no free courses in the seed (skipped)')

  // personal plan trial
  await p.goto(BASE + '/plans', { waitUntil: 'networkidle' })
  await shot('m1-07-plans')
  await p.getByRole('button', { name: /Start free trial|Subscribe/ }).click()
  await p.waitForURL(/checkout\/success\?subscription=/)
  const subId = new URL(p.url()).searchParams.get('subscription')
  console.log('  webhook:', stripe('subscription', subId).replace(/\n/g, ' '))
  await p.getByText(/free trial has started|Welcome to the Personal Plan/).waitFor({ timeout: 15000 })
  await p.goto(BASE + '/plans', { waitUntil: 'networkidle' })
  await p.getByText(/You're subscribed/).waitFor()
  step('personal plan trial started and shown on /plans')

  // included course → plan enrol
  await p.goto(BASE + '/courses', { waitUntil: 'networkidle' })
  const hrefs = await p.locator('main a[href^="/courses/"]').evaluateAll((as) => as.map((a) => a.getAttribute('href')))
  let planned = false
  for (const h of [...new Set(hrefs)]) {
    await p.goto(BASE + h, { waitUntil: 'networkidle' })
    if (await p.getByText('Included in your Personal Plan').count()) {
      await p.getByRole('button', { name: 'Start learning' }).click()
      await p.waitForURL(/\/learn\//)
      planned = true
      step(`plan enrol on ${h}`)
      break
    }
  }
  if (!planned) step('no plan-included course found (skipped)')

  // phone: filters drawer and cart
  const phone = await b.newContext({ ...devices['iPhone 14'], storageState: await ctx.storageState() })
  const q = await phone.newPage()
  q.on('pageerror', (e) => problems.push('phone pageerror: ' + e.message))
  await q.goto(BASE + '/courses', { waitUntil: 'networkidle' })
  await q.getByRole('button', { name: /^Filters/ }).click()
  await q.waitForTimeout(500)
  await q.screenshot({ path: `${OUT}/m1-08-phone-filters.png` })
  await q.getByRole('button', { name: /^Show/ }).click()
  await q.addInitScript(() => localStorage.setItem('theme', 'dark'))
  await q.goto(BASE + '/plans', { waitUntil: 'networkidle' })
  await q.waitForTimeout(600)
  await q.screenshot({ path: `${OUT}/m1-09-phone-plans-dark.png`, fullPage: true })
  const sw = await q.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth])
  assert(sw[0] <= sw[1], 'no sideways scroll on phone')
  step('phone filters drawer and plans (dark)')

  console.log(problems.length ? 'PROBLEMS:\n' + problems.join('\n') : 'no console errors, page errors or 5xx')
  await b.close()
  process.exit(problems.length ? 1 : 0)
})().catch((e) => {
  console.error('FAILED:', e.message.split('\n').slice(0, 6).join('\n'))
  process.exit(1)
})
