#!/usr/bin/env node
/**
 * Connect NOVA to an AI model: `npm run nova:setup`
 *
 * Asks which provider to use and (if needed) the API key, then writes the NOVA_*
 * settings into backend/.env on this computer. backend/.env is git-ignored, so the
 * key is never committed. Restart `npm run dev:sample` (or dev:full) afterwards.
 */
import { randomBytes } from 'node:crypto'
import { copyFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { createInterface } from 'node:readline'
import { fileURLToPath } from 'node:url'

const backend = join(dirname(fileURLToPath(import.meta.url)), '..', 'backend')
const envFile = join(backend, '.env')

const PROVIDERS = {
  1: {
    label: 'Groq (free key, fast, recommended)',
    base: 'https://api.groq.com/openai/v1',
    model: 'llama-3.3-70b-versatile',
    keyHelp: 'Create a free key at https://console.groq.com/keys (starts with gsk_)',
  },
  2: {
    label: 'Google Gemini (free tier)',
    base: 'https://generativelanguage.googleapis.com/v1beta/openai',
    model: 'gemini-2.0-flash',
    keyHelp: 'Create a key at https://aistudio.google.com/apikey',
  },
  3: {
    label: 'OpenAI (paid)',
    base: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    keyHelp: 'Create a key at https://platform.openai.com/api-keys (starts with sk-)',
  },
  4: {
    label: 'Ollama on this computer (free, private, slow on older PCs)',
    base: 'http://127.0.0.1:11434/v1',
    model: 'llama3.2:3b',
    keyHelp: null,
    timeout: '300',
  },
  5: { label: 'Turn the AI model off (basic look-up mode)', off: true },
}

const rl = createInterface({ input: process.stdin, output: process.stdout })
const ask = (q) => new Promise((resolve) => rl.question(q, (a) => resolve(a.trim())))

function askHidden(question) {
  return new Promise((resolve) => {
    const write = rl._writeToOutput
    rl._writeToOutput = (s) => write.call(rl, s.includes(question) ? s : s.replace(/[^\r\n]/g, '*'))
    rl.question(question, (answer) => {
      rl._writeToOutput = write
      process.stdout.write('\n')
      resolve(answer.trim())
    })
  })
}

function setVars(text, vars) {
  let out = text
  for (const [key, value] of Object.entries(vars)) {
    const line = `${key}=${value}`
    out = new RegExp(`^${key}=.*$`, 'm').test(out)
      ? out.replace(new RegExp(`^${key}=.*$`, 'm'), line)
      : `${out.trimEnd()}\n${line}\n`
  }
  return out
}

console.log('\nConnect NOVA to an AI model\n')
for (const [n, p] of Object.entries(PROVIDERS)) console.log(`  ${n}. ${p.label}`)
const choice = PROVIDERS[await ask('\nChoose 1-5 [1]: ') || '1']
if (!choice) {
  console.error('Unknown choice.')
  process.exit(1)
}

if (!existsSync(envFile)) {
  copyFileSync(join(backend, '.env.example'), envFile)
  writeFileSync(
    envFile,
    readFileSync(envFile, 'utf8').replace(
      /^SECRET_KEY=.*$/m,
      `SECRET_KEY=${randomBytes(48).toString('base64url')}`,
    ),
  )
}

let vars
if (choice.off) {
  vars = { NOVA_PROVIDER: 'none' }
} else {
  const model = (await ask(`Model [${choice.model}]: `)) || choice.model
  let key = ''
  if (choice.keyHelp) {
    console.log(`\n${choice.keyHelp}`)
    key = await askHidden('Paste the API key (hidden): ')
    if (!key) {
      console.error('No key entered; nothing changed.')
      process.exit(1)
    }
  } else {
    console.log(`\nInstall Ollama from https://ollama.com, then run:  ollama pull ${model}`)
  }
  vars = {
    NOVA_PROVIDER: 'openai_compatible',
    NOVA_BASE_URL: choice.base,
    NOVA_MODEL: model,
    NOVA_API_KEY: key,
    NOVA_TIMEOUT_SECONDS: choice.timeout ?? '60',
  }
}
writeFileSync(envFile, setVars(readFileSync(envFile, 'utf8'), vars))
rl.close()
console.log(
  `\nSaved to backend/.env (not tracked by git).\n` +
    `Now (re)start Orbit:  npm run dev:sample\n` +
    `Then open http://localhost:5173/app/nova (or 5174) and say hello.\n`,
)
