# Eranova Orbit API

FastAPI backend for Eranova Orbit. See the root [README](../README.md) for full
setup, and [`docs/architecture/overview.md`](../docs/architecture/overview.md)
for modules and endpoints.

## Quick start (PowerShell)

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
# Set SECRET_KEY in .env (generate with: python -c "import secrets; print(secrets.token_urlsafe(48))")
python -m scripts.dev_db start   # local PostgreSQL, no Docker
alembic upgrade head
python -m app.cli bootstrap
python -m app.cli create-superadmin
uvicorn app.main:create_app --factory --reload --port 8000
```

## Commands

| Command | Purpose |
| --- | --- |
| `ruff check .` / `ruff format .` | Lint / format |
| `pytest` | Unit, API and migration tests (needs `orbit_test`) |
| `alembic upgrade head` | Apply migrations |
| `python -m app.cli bootstrap` | Sync company, permissions and starter roles |
| `python -m app.cli create-superadmin` | Create the first Super Admin (interactive) |
| `python -m app.cli reset-password` | Operator password reset |
| `python -m app.cli purge-auth-records` | Retention clean-up |

## Package layout

```text
app/
  api/           health, pagination, deps, v1 router
  core/          config, logging, redaction, errors, middleware, security
  db/            declarative base, session, model registry
  modules/       company, identity, authorization, audit
  cli.py         operational commands
  main.py        create_app() factory
alembic/         migrations
tests/           unit/, api/, migration tests
```
