#!/usr/bin/env node
// `npm run db:start | db:stop | db:status` — wraps backend/scripts/dev_db.py.
import { spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const backend = join(dirname(fileURLToPath(import.meta.url)), '..', 'backend')
const python = join(
  backend,
  '.venv',
  process.platform === 'win32' ? 'Scripts\\python.exe' : 'bin/python',
)
const result = spawnSync(python, ['-m', 'scripts.dev_db', process.argv[2] ?? 'status'], {
  cwd: backend,
  stdio: 'inherit',
})
process.exit(result.status ?? 1)
