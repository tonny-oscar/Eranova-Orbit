# Eranova Orbit Web

React + Vite frontend for Eranova Orbit. See the root [README](../README.md)
for full setup.

## Quick start (PowerShell)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite proxy forwards `/api`, `/health` and
`/ready` to `http://localhost:8000`.

If npm fails with a TLS certificate error, set `$env:NODE_OPTIONS="--use-system-ca"`.

## Scripts

| Script                            | Purpose                                                           |
| --------------------------------- | ----------------------------------------------------------------- |
| `npm run dev`                     | Development server                                                |
| `npm run build`                   | Production build to `dist/`                                       |
| `npm run lint`                    | ESLint                                                            |
| `npm run format` / `format:check` | Prettier                                                          |
| `npm test`                        | Vitest component and flow tests                                   |
| `npm run test:e2e`                | Playwright (needs a running API and `E2E_EMAIL` / `E2E_PASSWORD`) |

## Source layout

```text
src/
  app/           providers, routes, query client
  components/    design-system UI and brand
  features/      auth, dashboard, settings, admin, navigation
  layouts/       command-centre shell
  lib/           API client and utilities
  routes/        public and error pages
  styles/        Tailwind design tokens
```
