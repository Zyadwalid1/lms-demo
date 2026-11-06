// M2 end-to-end: a new learner enrols in a course with one lecture of every kind and
// works through it in the player: placeholder video, reading, link, live session, quiz
// (every answer type, review), assignment (marked by the instructor), notes, Q&A,
// review, course completion, certificate + public verification, notifications,
// achievements, settings and support. Desktop, then phone.
const { chromium, devices } = require('playwright')
const assert = require('assert')
const OUT = process.argv[2] || 'shots'
require('fs').mkdirSync(OUT, { recursive: true })
const { BASE, py: run, lastLine, NEW_USER_PASSWORD } = require('./lib')
const py = (script, ...args) => lastLine(run(script, ...args))

;(async () => {
  const b = await chromium.launch()
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } })
  const p = await ctx.newPage()
  global.page = p
  const problems = []
  p.on('pageerror', (e) => problems.push('pageerror: ' + e.message))
  let expect400 = false // the wrong-password check answers 400 on purpose
  p.on('console', (m) => m.type() === 'error' && !/status of (401|404)/.test(m.text()) && !(expect400 && /status of 400/.test(m.text())) && !/playerjs|mediadelivery/.test(m.text()) && problems.push('console: ' + m.text()))
  p.on('response', (r) => r.url().includes('/api/') && r.status() >= 500 && problems.push(`HTTP ${r.status()} ${r.url()}`))
  const step = (s) => console.log('✓', s)
  const shot = async (n) => (await p.waitForTimeout(600), p.screenshot({ path: `${OUT}/${n}.png` }))
  const toast = (t) => p.locator('[data-sonner-toast]').filter({ hasText: t }).first().waitFor()
  const next = async () => {
    await p.locator('#next-lecture').click()
    await p.waitForTimeout(400)
  }
  const complete = async () => {
    await p.getByRole('button', { name: 'Mark as complete' }).first().click()
    await p.getByText('Completed', { exact: true }).first().waitFor()
  }

  const slug = py('e2e_course.py')
  const email = py('e2e_user.py', NEW_USER_PASSWORD)
  console.log('  course:', slug, ' learner:', email)
  await p.goto(BASE + '/login')
  await p.getByLabel('Email').fill(email)
  await p.getByLabel('Password').fill(NEW_USER_PASSWORD)
  await p.getByRole('button', { name: 'Log in' }).click()
  await p.waitForURL(/\/learn$/)

  // a course you are not enrolled in sends you to its page
  await p.goto(`${BASE}/learn/${slug}`)
  await p.waitForURL(new RegExp(`/courses/${slug}$`))
  await p.getByRole('button', { name: /Enrol for free/ }).click()
  await p.waitForURL(new RegExp(`/learn/${slug}/lecture/`))
  step('enrol from the course page lands in the player')

  // 1. video not uploaded yet: placeholder, completed by hand
  await p.getByText('This video is on its way').waitFor()
  await shot('m2-01-player-video-placeholder')
  await p.getByRole('button', { name: 'Mark as complete' }).click()
  await toast('Marked as complete')
  await p.getByText(/1 of 6 done/).waitFor()
  step('placeholder video completed, header progress 1 of 6')

  // notes pinned to the lecture
  await p.getByRole('tab', { name: 'Notes' }).click()
  await p.getByLabel('New note').fill('Remember: serializers validate input.')
  await p.getByRole('button', { name: 'Save note' }).click()
  await p.getByText('Remember: serializers validate input.').waitFor()
  step('note saved')

  // 2. reading
  await next()
  await p.getByRole('heading', { name: 'Why it matters' }).first().waitFor()
  await p.getByText(/min read/).waitFor()
  await shot('m2-02-reading')
  await complete()
  step('reading rendered and completed')

  // 3. external link
  await next()
  const link = p.getByRole('link', { name: /Open link/ })
  assert.strictEqual(await link.getAttribute('target'), '_blank')
  assert.match(await link.getAttribute('rel'), /noopener/)
  await complete()
  step('external link (new tab, noopener) completed')

  // 4. live session: starts in 10 min, so the join link is already there
  await next()
  await p.getByRole('link', { name: /Join the session/ }).waitFor()
  await p.getByText(/Starts in/).waitFor()
  await shot('m2-03-live-session')
  step('live session shows countdown and join link')

  // 5. quiz: every answer type, then review
  await next()
  await p.getByText('Pass mark').waitFor()
  await shot('m2-04-quiz-intro')
  await p.getByRole('button', { name: 'Start quiz' }).click()
  await p.getByRole('timer').waitFor()
  for (let i = 0; i < 5; i++) {
    const prompt = await p.locator('section[aria-labelledby^="q-"]').innerText()
    if (/2 \+ 2/.test(prompt)) await p.getByRole('radio', { name: '4' }).click()
    else if (/frameworks/.test(prompt)) {
      await p.getByRole('checkbox', { name: 'Django' }).click()
      await p.getByRole('checkbox', { name: 'Flask' }).click()
    } else if (/stateless/.test(prompt)) await p.getByRole('radio', { name: 'True' }).click()
    else if (/status codes/.test(prompt)) {
      await p.getByLabel('Match for 200').selectOption('OK')
      await p.getByLabel('Match for 404').selectOption('Not Found')
    } else if (/method sends/.test(prompt)) await p.getByLabel('Blank 1').fill('post')
    else throw new Error('unknown question: ' + prompt)
    if (i === 2) await shot('m2-05-quiz-question')
    if (i < 4) await p.getByRole('button', { name: 'Next', exact: true }).click()
  }
  await p.getByText('5 of 5 answered').waitFor()
  await p.getByRole('button', { name: 'Submit answers' }).click()
  await p.getByText('You passed').waitFor()
  await p.getByText('Review your answers').waitFor()
  assert.strictEqual(await p.locator('li').filter({ hasText: 'Your answer' }).count() >= 1, true)
  await shot('m2-06-quiz-result')
  step('quiz: 5 answer types, passed, review shown')

  // 6. assignment: submit, then the instructor marks it
  await next()
  await p.getByText('How it\'s marked').waitFor()
  await p.getByLabel('Link to your work').fill('http://insecure.example.com')
  await p.getByText('Links must start with https://').waitFor()
  await p.getByLabel('Link to your work').fill('https://github.com/example/api')
  await p.getByLabel('Your answer').fill('Resources are nouns, verbs are HTTP methods.')
  await p.getByRole('button', { name: 'Submit', exact: true }).click()
  await toast('Submitted')
  await p.getByText('Waiting for marking').first().waitFor()
  await shot('m2-07-assignment-submitted')
  py('e2e_grade.py', email, slug)
  await p.reload()
  await p.getByText('Instructor feedback').waitFor()
  await p.getByText('85 / 100').waitFor()
  step('assignment submitted, marked, feedback shown')

  // Q&A: ask, answer, vote
  await p.getByRole('tab', { name: /Q&A/ }).click()
  await p.getByRole('button', { name: 'Ask a question' }).click()
  await p.getByRole('textbox', { name: 'Question', exact: true }).fill('Should IDs be UUIDs?')
  await p.getByLabel('Details (optional)').fill('Thinking about public URLs.')
  await p.getByRole('button', { name: 'Post question' }).click()
  await p.waitForURL(/\/qa\//)
  await p.getByRole('heading', { name: 'Should IDs be UUIDs?' }).waitFor()
  await p.getByLabel('Your answer').fill('Yes, they are not guessable.')
  await p.getByRole('button', { name: 'Post answer' }).click()
  await p.getByText('Yes, they are not guessable.').waitFor()
  assert.strictEqual(await p.getByRole('button', { name: 'I have this question too' }).count(), 0, 'no upvoting your own question')
  await shot('m2-08-qa-thread')
  await p.getByRole('button', { name: 'All questions' }).click()
  await p.getByRole('button', { name: /Should IDs be UUIDs/ }).waitFor()
  step('Q&A: asked, answered (no self-vote), back to list')

  // review
  await p.getByRole('tab', { name: 'Review' }).click()
  await p.getByRole('radio', { name: '5 stars' }).click()
  await p.getByLabel('Tell others why (optional)').fill('Every lecture type in one place.')
  await p.getByRole('button', { name: 'Post review' }).click()
  await toast('Thanks for your review')
  await p.getByRole('button', { name: 'Update review' }).waitFor()
  step('review posted (and editable)')

  // 7. finish: the live session is the last one left -> celebration + certificate
  await p.getByText(/5 of 6 done/).waitFor()
  await p.getByRole('link', { name: /Live Q&A/ }).first().click()
  await p.getByRole('link', { name: /Join the session/ }).waitFor()
  await p.getByRole('button', { name: 'Mark as complete' }).click()
  await p.getByRole('dialog', { name: 'You finished the course!' }).waitFor()
  await p.getByRole('link', { name: 'Download certificate' }).waitFor()
  await p.waitForTimeout(400)
  await shot('m2-09-course-complete')
  const pdfHref = await p.getByRole('link', { name: 'Download certificate' }).getAttribute('href')
  const pdf = await p.request.get(BASE + pdfHref)
  assert.strictEqual(pdf.status(), 200)
  assert.strictEqual(pdf.headers()['content-type'], 'application/pdf')
  await p.keyboard.press('Escape')
  step('course complete: celebration, certificate PDF downloads')

  // certificates, public verification (signed out too), notifications, achievements
  await p.goto(BASE + '/learn/certificates')
  await p.getByText('Every Lecture Type (E2E)').first().waitFor()
  await shot('m2-10-certificates')
  const verifyHref = await p.getByRole('link', { name: /Verify/ }).first().getAttribute('href')
  const anon = await b.newContext()
  const ap = await anon.newPage()
  await ap.goto(BASE + verifyHref)
  await ap.getByText('Genuine certificate, issued by LearnHub').waitFor()
  await ap.screenshot({ path: `${OUT}/m2-11-verify-public.png` })
  await ap.goto(BASE + '/verify/LH-NOPE-NOPE-NOPE')
  await ap.getByText('No certificate with this code').waitFor()
  await anon.close()
  step('certificate listed; public verify works signed out; unknown code refused')

  await p.goto(BASE + '/learn')
  const bell = p.getByRole('button', { name: /Notifications, \d+ unread/ })
  await bell.waitFor()
  await bell.click()
  await p.getByText(/Your certificate for Every Lecture Type/).waitFor()
  await shot('m2-12-bell')
  await p.getByText('Your work has been marked').click()
  await p.waitForURL(/\/lecture\//)
  await p.getByText('Instructor feedback').waitFor()
  step('bell: unread count, list, opening one goes to the marked assignment')

  await p.goto(BASE + '/notifications')
  await p.getByRole('button', { name: 'Mark all read' }).click()
  await p.getByRole('button', { name: 'Notifications', exact: true }).waitFor()
  await p.goto(BASE + '/learn/achievements')
  await p.getByText('First course', { exact: true }).waitFor()
  await p.getByText(/Earned/).first().waitFor()
  await shot('m2-13-achievements')
  step('notifications all read; "First course" and "Critic" badges earned')

  // settings: profile, notification preference, wrong current password
  await p.goto(BASE + '/account')
  await p.getByLabel('Full name').fill('Eve Learner')
  await p.getByRole('button', { name: 'Save changes' }).click()
  await toast('Profile saved')
  const sw = p.getByRole('switch', { name: /by email/ }).first()
  const before = await sw.getAttribute('aria-checked')
  await sw.click()
  await p.waitForTimeout(500)
  await p.reload()
  assert.notStrictEqual(await p.getByRole('switch', { name: /by email/ }).first().getAttribute('aria-checked'), before, 'preference saved')
  await p.getByLabel('Current password').fill('wrong-password-1')
  await p.getByLabel('New password').fill('another-pass-5678')
  expect400 = true
  await p.getByRole('button', { name: 'Change password' }).click()
  await p.locator('p.text-danger').first().waitFor()
  expect400 = false
  assert(!(await p.getByText('Password changed').isVisible()), 'wrong current password refused')
  await shot('m2-14-settings')
  step('settings: name saved, preference persisted, wrong password refused')

  // support
  await p.goto(BASE + '/support')
  await p.getByRole('button', { name: 'New request' }).click()
  await p.getByLabel('Subject').fill('Invoice for my company')
  await p.getByLabel('Message').fill('Please send a VAT invoice.')
  await p.getByRole('button', { name: 'Send', exact: true }).click()
  await p.waitForURL(/\/support\//)
  await p.getByLabel('Reply').fill('Our VAT number is GB123.')
  await p.getByRole('button', { name: 'Send reply' }).click()
  await p.getByText('Our VAT number is GB123.').waitFor()
  await shot('m2-15-support-thread')
  step('support: request opened and replied to')

  // the progress shows on My learning
  await p.goto(BASE + '/learn')
  await p.getByText('100%').first().waitFor()
  step('My learning shows 100%')

  // phone: player with drawer and content tab
  const phone = await b.newContext({ ...devices['iPhone 13'] })
  await phone.addCookies(await ctx.cookies())
  const m = await phone.newPage()
  m.on('pageerror', (e) => problems.push('phone pageerror: ' + e.message))
  await m.goto(`${BASE}/learn/${slug}`)
  await m.waitForURL(/\/lecture\//)
  await m.getByRole('tab', { name: 'Content' }).waitFor()
  await m.screenshot({ path: `${OUT}/m2-16-phone-player.png` })
  await m.getByRole('button', { name: 'Course content' }).click()
  const drawer = m.getByRole('dialog', { name: 'Course content' })
  await drawer.getByRole('button', { name: /Section 1: Watch and read/ }).click()
  await drawer.getByRole('link', { name: /A reading/ }).click()
  await m.getByRole('heading', { name: 'Why it matters' }).first().waitFor()
  await m.screenshot({ path: `${OUT}/m2-17-phone-reading.png` })
  await m.goto(BASE + '/account')
  await m.getByRole('navigation', { name: 'Account' }).getByRole('link', { name: 'Certificates' }).waitFor()
  await phone.close()
  step('phone: drawer navigation, account shortcuts')

  await b.close()
  if (problems.length) {
    console.log('PROBLEMS:\n' + problems.join('\n'))
    process.exit(1)
  }
  console.log('M2 E2E passed, no console errors or 5xx')
})().catch(async (e) => {
  console.error('FAILED:', e.message)
  if (global.page) await global.page.screenshot({ path: `${OUT}/m2-FAILED.png` }).catch(() => {})
  process.exit(1)
})
