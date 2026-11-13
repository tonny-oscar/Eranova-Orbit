#!/usr/bin/env node
/**
 * One-command local development: `npm run dev:full`
 * (`npm run dev:sample` also loads clearly labelled sample data on first run)
 *
 *  1. starts the local PostgreSQL (backend/scripts/dev_db.py, no Docker)
 *  2. creates backend/.env with a random local SECRET_KEY if it does not exist
 *  3. applies migrations and bootstraps roles/permissions
 *  4. runs the API (http://localhost:8000), the background worker and the web app
 *     (http://localhost:5173)
 *
 * Sign-in is skipped locally (DEV_AUTO_LOGIN=true for this process only).
 * Press Ctrl+C to stop the API and web app; the database keeps running
 * (stop it with `npm run db:stop`).
 */
import { spawn, spawnSync } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { copyFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const backend = join(root, 'backend')
const frontend = join(root, 'frontend')
const isWindows = process.platform === 'win32'
const python = join(backend, '.venv', isWindows ? 'Scripts\\python.exe' : 'bin/python')

function fail(message) {
  console.error(`\n✖ ${message}\n`)
  process.exit(1)
}

function step(label, command, args, cwd, env = {}) {
  console.log(`\n▶ ${label}`)
  const result = spawnSync(command, args, {
    cwd,
    stdio: 'inherit',
    env: { ...process.env, ...env },
    shell: false,
  })
  if (result.status !== 0) fail(`${label} failed.`)
}

if (!existsSync(python)) {
  fail(
    'Python virtual environment not found. Run these once in backend\\:\n' +
      '  py -3.12 -m venv .venv\n  .\\.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt',
  )
}

const envFile = join(backend, '.env')
if (!existsSync(envFile)) {
  copyFileSync(join(backend, '.env.example'), envFile)
  const secret = randomBytes(48).toString('base64url')
  writeFileSync(
    envFile,
    readFileSync(envFile, 'utf8').replace(/^SECRET_KEY=.*$/m, `SECRET_KEY=${secret}`),
  )
  console.log('Created backend/.env with a random local SECRET_KEY.')
}

const devEnv = {
  DEV_AUTO_LOGIN: 'true',
  ENVIRONMENT: 'local',
  // Vite moves to 5174 when 5173 is taken (e.g. by `npm run dev:demo`).
  CORS_ALLOWED_ORIGINS: 'http://localhost:5173,http://localhost:5174',
}
step('Starting local PostgreSQL', python, ['-m', 'scripts.dev_db', 'start'], backend)
step('Applying database migrations', python, ['-m', 'alembic', 'upgrade', 'head'], backend, devEnv)
step('Bootstrapping roles and permissions', python, ['-m', 'app.cli', 'bootstrap'], backend, devEnv)
if (process.argv.includes('--sample')) {
  step('Loading labelled sample data', python, ['-m', 'app.demo_seed'], backend, devEnv)
}

const children = []
function run(label, command, args, cwd, env = {}) {
  const child = spawn(command, args, {
    cwd,
    stdio: 'inherit',
    env: { ...process.env, ...env },
    shell: isWindows && command === 'npm',
  })
  child.on('exit', (code) => {
    console.log(`${label} exited (${code}).`)
    shutdown()
  })
  children.push(child)
}

function shutdown() {
  for (const child of children) if (!child.killed) child.kill()
  process.exit(0)
}
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)

console.log('\n▶ Starting API on http://localhost:8000 and web app on http://localhost:5173\n')
run(
  'API',
  python,
  ['-m', 'uvicorn', 'app.main:create_app', '--factory', '--reload', '--port', '8000'],
  backend,
  devEnv,
)
run('Worker', python, ['-m', 'app.worker'], backend, { ENVIRONMENT: 'local' })
run('Web app', 'npm', ['run', 'dev'], frontend)
