// Shared helpers for the E2E scripts (HARNESS ONLY - never imported by the app).
const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')

const ROOT = path.resolve(__dirname, '..', '..')
const BACKEND = path.join(ROOT, 'backend')
const PY =
  process.env.LMS_PYTHON ||
  [path.join(BACKEND, '.venv', 'Scripts', 'python.exe'), path.join(BACKEND, '.venv', 'bin', 'python')].find((p) => fs.existsSync(p)) ||
  'python'

/** Load backend/.env.e2e (database URLs of the disposable e2e database) into this process. */
function e2eEnv() {
  const file = path.join(BACKEND, '.env.e2e')
  if (!fs.existsSync(file)) throw new Error('backend/.env.e2e is missing: see tools/harness/README.md (E2E never uses the shared dev database).')
  const env = {}
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/)
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, '')
  }
  return env
}

/** Run a harness Python script against the e2e database; returns its output. */
function py(script, ...args) {
  return execFileSync(PY, [path.join(__dirname, script), ...args], {
    cwd: BACKEND,
    env: { ...process.env, ...e2eEnv(), PYTHONPATH: BACKEND },
  }).toString().trim()
}
const lastLine = (s) => s.split(/\r?\n/).pop().trim()

module.exports = {
  ROOT,
  BACKEND,
  PY,
  e2eEnv,
  py,
  lastLine,
  BASE: process.env.E2E_BASE || 'http://localhost:5173',
  // password for the throw-away users the scripts create (not a real account)
  NEW_USER_PASSWORD: 'e2e-pass-1234',
  // a seeded company admin, for checks that need existing data (password from the user)
  DEMO_EMAIL: process.env.E2E_DEMO_EMAIL || 'hana.cole@brightwater.example.com',
  DEMO_PASSWORD: process.env.E2E_DEMO_PASSWORD,
}
