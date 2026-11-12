# Deployment and environments

## Environments

| Environment | Frontend | API | Database | Notes |
| --- | --- | --- | --- | --- |
| Local | Vite dev server :5173 | uvicorn :8000 | Docker `orbit_dev` (:5433) | `.env` files, never committed |
| Staging / preview | Vercel preview deployments | Render `orbit-api-staging` | Render `orbit-db-staging` | Own secrets; never points at production data |
| Production | Vercel production | Render `orbit-api-production` | Render `orbit-db-production` | Protected branch, paid plans |

Each environment has its own database, `SECRET_KEY`, and (later) AI and integration
credentials.

## Render (API)

`render.yaml` defines the staging API and database. For production, duplicate the
service and database with `-production` names (or create them in the dashboard) using
the same commands.

- **Build:** `pip install -r requirements.txt`
- **Pre-deploy (controlled migration):** `alembic upgrade head && python -m app.cli bootstrap`
- **Start:** `uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*" --no-server-header`
- **Health check:** `/ready`

Required environment variables (see `backend/.env.example`):

| Variable | Staging / production value |
| --- | --- |
| `ENVIRONMENT` | `staging` or `production` |
| `DATABASE_URL` | From the Render database (internal URL) |
| `SECRET_KEY` | Unique random value per environment (`generateValue: true`) |
| `SESSION_COOKIE_SECURE` | `true` (startup fails otherwise) |
| `CORS_ALLOWED_ORIGINS` | Exact frontend origin(s), comma-separated |
| `SESSION_COOKIE_DOMAIN` | Leave empty (recommended host-only `__Host-` cookie) |

The app refuses to start in staging/production with an insecure cookie setting or a
placeholder secret.

After the first deploy, open a Render shell and run `python -m app.cli create-superadmin`.

> Render's free PostgreSQL instances expire and free web services sleep. Use paid plans
> for production.

## Vercel (frontend)

- Project root: `frontend/`. Build `npm run build`, output `dist` (in `vercel.json`).
- `vercel.json` adds the SPA fallback, security headers (CSP, HSTS, frame denial) and
  immutable caching for hashed assets.
- Only `VITE_*` variables reach the browser. Never put secrets there.

### Choose one API topology (see ADR 0003)

**A. Custom subdomains (recommended)**

1. Add `orbit.<domain>` to Vercel and `api.orbit.<domain>` to the Render service.
2. Vercel env: `VITE_API_BASE_URL=https://api.orbit.<domain>`.
3. Render env: `CORS_ALLOWED_ORIGINS=https://orbit.<domain>`.
4. In `vercel.json`, change the CSP `connect-src` to `'self' https://api.orbit.<domain>`.

**B. Vercel rewrite proxy (no custom domain yet)**

1. Add this as the **first** rewrite in `vercel.json`:
   `{ "source": "/api/:path*", "destination": "https://<render-service>.onrender.com/api/:path*" }`
2. Leave `VITE_API_BASE_URL` empty.
3. Render env: `CORS_ALLOWED_ORIGINS=https://<project>.vercel.app` (plus preview origins
   if needed).

## Release checklist

1. CI green on the pull request (lint, tests including migrations, build, dependency audit).
2. Confirm a recent database backup exists (Render automatic backups on paid plans).
3. Merge to `main`. Render runs the pre-deploy migration, then switches traffic.
4. Smoke test:
   - `GET https://<api>/ready` returns `{"status": "ready"}`
   - sign in, load the overview, sign out
   - `GET /api/v1/auth/me` without a cookie returns 401
5. Watch logs for `level: ERROR` filtered by correlation ID.

## Rollback

- **Application:** use Render's "Rollback" to the previous deploy, and Vercel's "Instant
  Rollback" on the previous production deployment.
- **Schema:** migrations are written to be backward compatible with the previous app
  version where possible. If a migration must be reversed, run
  `alembic downgrade -1` from a Render shell **after** taking a backup, then roll back
  the app. Never edit production schema by hand.
- **Data:** restore from the Render backup into a new database, verify, then repoint
  `DATABASE_URL`.

## Retention job

Schedule `python -m app.cli purge-auth-records` daily (Render cron job) once background
services are introduced.
