# Eranova Orbit

**One company. One command centre.**

Eranova Orbit is Eranova Technologies' company operating platform: a public product
marketplace plus a private command centre for products, teams, customers, projects,
marketing, analytics, support and reporting, with **NOVA** as the company AI assistant.

The authoritative requirements are in [`docs/requirements/`](docs/requirements/):

- [Master engineering brief](docs/requirements/ERANOVA_ORBIT_MASTER_PROMPT.md)
- [Technical architecture](docs/requirements/ERANOVA_ORBIT_TECHNICAL_ARCHITECTURE.md)

## Quick look without a database (demo preview)

```powershell
npm install
npm run dev:demo
```

Open http://localhost:5173. Sign-in is bypassed (you are a demo Super Admin) and all data is
in-memory sample data, labelled by a banner. Nothing is saved. See
[ADR 0010](docs/adr/0010-frontend-demo-preview.md).

## Current status: Phases 1–4 (Foundation, Marketplace, Operations, Integrations)

| Area | Delivered |
| --- | --- |
| Backend | FastAPI modular monolith, async SQLAlchemy 2 + Alembic, structured JSON logs with correlation IDs, consistent error envelope, `/health` and `/ready` |
| Identity | Email/password sign-in (Argon2id), server-side sessions in HttpOnly cookies, CSRF protection, idle + absolute expiry, login throttling, password change, administrator-issued temporary passwords with forced change |
| Authorization | Permission catalogue (`resource.action`), 13 customisable starter roles plus custom roles, scoped assignments (company / department / product / own; project scope arrives with projects), privilege-escalation guards |
| Product registry | Register and edit products, lifecycle status with history, team roster, product-scoped access, "awaiting confirmation" labelling for unverified details |
| People | User administration (create, disable, reset), departments, minimal work profiles (department, title, manager, employment type, start date) |
| Command centre | Live permission-scoped overview (products, people, accounts, recent activity) with source and timestamp, global search (Ctrl/⌘+K) |
| Public marketplace | Home, product catalogue with search/category filter, product pages (features, pricing), pricing page, CMS-managed pages, contact and demo forms |
| Website content | Staff editor with drafts and approval-gated publishing; products publish only when confirmed, public-status and described |
| Leads | Every valid enquiry creates or updates a lead (consent + privacy-notice version, UTM attribution, spam protection); staff lead list and detail |
| CRM | Configurable pipeline stages and board, activities timeline, lead → customer conversion, customers with contacts and product subscriptions, CSV exports |
| Delivery work | Projects, members, milestones, tasks with subtasks, dependencies, comments, links and a review workflow (no self-approval); project-scoped access |
| Employee portal | My work, leave requests with approvals, transparent self check-in attendance, in-app notifications |
| Integrations | Connect live products (Orbit product API), GitHub, Vercel, Google Analytics 4 and uptime monitors; signed webhooks, sync history, freshness and failure states; secrets stay in `INTEGRATION_*` environment variables |
| Monitoring and analytics | Uptime, latency, TLS expiry and deployments kept separate from marketing analytics; every number shows its source and last update |
| Worker | `python -m app.worker`: scheduled syncs, follow-up and task reminders, retention |
| Audit | Append-only audit log (database trigger blocks UPDATE/DELETE/TRUNCATE) for sign-ins, denials and every privileged change |
| Delivery | Docker-free local PostgreSQL and one-command dev runner, CI workflow, Render blueprint, Vercel config, ADRs and operations docs |

Marketing campaigns, support, documents, reports, finance and NOVA arrive in later phases
(see the phase list in the master brief). The navigation only shows modules that exist.
To connect your existing live products, follow the
[product integration contract](docs/integrations/product-api-contract.md).

> Before launch: write and legally review the privacy notice, then publish it from
> **Website → Privacy notice** (Kenya Data Protection Act).

## Repository layout

```text
backend/            FastAPI API (app/, alembic/, tests/)
frontend/           React + Vite web app (src/, tests/, e2e/)
docs/
  requirements/     Authoritative product and architecture briefs
  adr/              Architecture decision records
  architecture/     Current system overview
  operations/       Local setup, deployment, runbooks
scripts/            One-command dev runner and local database helpers
render.yaml         Render blueprint (API + database)
```

## Prerequisites (Windows)

- Python 3.12, Node.js 22+ (24 recommended), Git
- **No Docker and no PostgreSQL installation needed.** A local PostgreSQL 16 ships inside
  the `pgserver` Python package (a dev dependency) and runs from your user profile.

> **OneDrive note:** this folder is inside OneDrive. Syncing `node_modules`, `.venv` and
> `.git` causes slow installs and file-lock errors. Moving the project to a non-synced
> folder such as `C:\dev\eranova-orbit` before creating the Git repository is strongly
> recommended.

## Local development

### One-time setup

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd ..
npm install
```

### Every day: one command

```powershell
npm run dev:full
```

This starts the local database, creates `backend\.env` (with a random local secret) the
first time, applies migrations, bootstraps roles, and runs the API (http://localhost:8000)
and the web app (http://localhost:5173). **Sign-in is skipped locally**: you are signed in
as the first Super Admin, or a "Local Developer" Super Admin is created on an empty
database. The bypass works only when `ENVIRONMENT=local`; the API refuses to start with it
anywhere else.

Database commands: `npm run db:start`, `npm run db:stop`, `npm run db:status`. Data is
kept in `%LOCALAPPDATA%\EranovaOrbit\pgdata` (outside OneDrive) on port **5433**, with
databases `orbit_dev` and `orbit_test`.

### Manual backend commands (PowerShell, from `backend\`)

```powershell
.\.venv\Scripts\Activate.ps1
python -m scripts.dev_db start
alembic upgrade head
python -m app.cli bootstrap
python -m app.cli create-superadmin      # a real account with your own password
uvicorn app.main:create_app --factory --reload --port 8000
```

Command Prompt (differences only):

```bat
.venv\Scripts\activate.bat
copy .env.example .env
```

API docs (local/staging only): http://localhost:8000/docs

### 3. Frontend

From the repository root (the root `package.json` forwards to `frontend/`):

```powershell
npm install
npm run dev
```

The same commands also work inside `frontend\`.

Open http://localhost:5173. The Vite dev server proxies `/api`, `/health` and `/ready` to
the backend so the session cookie stays first-party.

If npm fails with `UNABLE_TO_VERIFY_LEAF_SIGNATURE` (antivirus/proxy TLS inspection), run
it with the Windows certificate store: PowerShell `$env:NODE_OPTIONS="--use-system-ca"`,
CMD `set NODE_OPTIONS=--use-system-ca`.

## Quality checks

```powershell
# Backend (from backend/, venv active; PostgreSQL must be running for API/migration tests)
ruff check .
ruff format --check .
pytest

# Frontend (from frontend/)
npm run lint
npm run format:check
npm test
npm run build
```

### End-to-end tests

With the backend and database running and a test account created:

```powershell
cd frontend
npx playwright install chromium
$env:E2E_EMAIL="you@eranova.co.ke"; $env:E2E_PASSWORD="..."
npm run test:e2e
```

## Operations commands

| Command (from `backend/`) | Purpose |
| --- | --- |
| `python -m app.cli bootstrap` | Ensure the company record, sync the permission catalogue and create starter roles (idempotent) |
| `python -m app.cli create-superadmin` | Interactively create a Super Admin (prompts for password; nothing on the command line) |
| `python -m app.cli reset-password` | Set a temporary password for a user (they must change it) and revoke all their sessions |
| `python -m app.cli purge-auth-records` | Apply retention to login attempts and expired sessions |
| `python -m app.cli register-initial-products` | Register ShulePoa, HostPilot, OTPGuard, SitePoa and MenuPoa as unconfirmed drafts (names only, idempotent) |

Day-to-day user administration (creating accounts, resetting passwords, assigning roles)
is done in the app under **Administration → Users**.

## Documentation

- [Architecture overview](docs/architecture/overview.md)
- [Architecture decision records](docs/adr/)
- [Deployment and environments](docs/operations/deployment.md)
- [API reference](docs/api/README.md)
- [Product integration contract](docs/integrations/product-api-contract.md)
