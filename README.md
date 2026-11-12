# Eranova Orbit

**One company. One command centre.**

Eranova Orbit is Eranova Technologies' company operating platform: a public product
marketplace plus a private command centre for products, teams, customers, projects,
marketing, analytics, support and reporting, with **NOVA** as the company AI assistant.

The authoritative requirements are in [`docs/requirements/`](docs/requirements/):

- [Master engineering brief](docs/requirements/ERANOVA_ORBIT_MASTER_PROMPT.md)
- [Technical architecture](docs/requirements/ERANOVA_ORBIT_TECHNICAL_ARCHITECTURE.md)

## Current status: Phase 1 — Foundation and Core Orbit

| Area | Delivered |
| --- | --- |
| Backend | FastAPI modular monolith, async SQLAlchemy 2 + Alembic, structured JSON logs with correlation IDs, consistent error envelope, `/health` and `/ready` |
| Identity | Email/password sign-in (Argon2id), server-side sessions in HttpOnly cookies, CSRF protection, idle + absolute expiry, login throttling, password change, administrator-issued temporary passwords with forced change |
| Authorization | Permission catalogue (`resource.action`), 13 customisable starter roles plus custom roles, scoped assignments (company / department / product / own; project scope arrives with projects), privilege-escalation guards |
| Product registry | Register and edit products, lifecycle status with history, team roster, product-scoped access, "awaiting confirmation" labelling for unverified details |
| People | User administration (create, disable, reset), departments, minimal work profiles (department, title, manager, employment type, start date) |
| Command centre | Live permission-scoped overview (products, people, accounts, recent activity) with source and timestamp, global search (Ctrl/⌘+K) |
| Audit | Append-only audit log (database trigger blocks UPDATE/DELETE/TRUNCATE) for sign-ins, denials and every privileged change |
| Delivery | Docker Compose PostgreSQL, CI workflow, Render blueprint, Vercel config, ADRs and operations docs |

CRM, projects, marketing, analytics, support, finance and NOVA arrive in later phases (see
the phase list in the master brief). The navigation only shows modules that exist.

## Repository layout

```text
backend/            FastAPI API (app/, alembic/, tests/)
frontend/           React + Vite web app (src/, tests/, e2e/)
docs/
  requirements/     Authoritative product and architecture briefs
  adr/              Architecture decision records
  architecture/     Current system overview
  operations/       Local setup, deployment, runbooks
infra/postgres/     Local database init scripts
docker-compose.yml  Local PostgreSQL 16
render.yaml         Render blueprint (API + database)
```

## Prerequisites (Windows)

- Python 3.12, Node.js 22+ (24 recommended), Git
- Docker Desktop with WSL 2 (for local PostgreSQL). If Docker reports
  "WSL 2 kernel file is not found", run `wsl --update` in an **Administrator** PowerShell
  and restart Docker Desktop.

> **OneDrive note:** this folder is inside OneDrive. Syncing `node_modules`, `.venv` and
> `.git` causes slow installs and file-lock errors. Moving the project to a non-synced
> folder such as `C:\dev\eranova-orbit` before creating the Git repository is strongly
> recommended.

## Local development

### 1. Start PostgreSQL

```powershell
docker compose up -d postgres
```

This creates `orbit_dev` (development) and `orbit_test` (automated tests) on port **5433**.

### 2. Backend

PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
# Edit .env and set SECRET_KEY. Generate one with:
python -c "import secrets; print(secrets.token_urlsafe(48))"
alembic upgrade head
python -m app.cli bootstrap
python -m app.cli create-superadmin
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
