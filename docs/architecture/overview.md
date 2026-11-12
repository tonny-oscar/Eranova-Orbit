# Architecture overview (as built)

This describes what exists in the codebase today. The target architecture is in
[`docs/requirements/ERANOVA_ORBIT_TECHNICAL_ARCHITECTURE.md`](../requirements/ERANOVA_ORBIT_TECHNICAL_ARCHITECTURE.md).

## Request path

```text
Browser ── Vercel (static React app) ──HTTPS── Render: FastAPI (uvicorn)
                                                  │
                     RequestContextMiddleware (correlation ID, security headers, request log)
                     CORSMiddleware (credentialed, allow-listed origins)
                     OriginCheckMiddleware (rejects cross-site unsafe requests)
                                                  │
                     /api/v1 routers ── deps: session cookie → CSRF → principal → permission
                                                  │
                     services (business rules, audit events, explicit commits)
                                                  │
                                       PostgreSQL 16 (Orbit database)
```

## Backend modules (`backend/app/modules`)

| Module | Responsibility | Tables |
| --- | --- | --- |
| `company` | Tenant boundary (Eranova today; `company_id` on owned records) | `companies` |
| `identity` | Users, password hashing, sessions, login throttling, password change/reset | `users`, `sessions`, `login_attempts` |
| `authorization` | Permission catalogue, roles, scoped assignments, pure policy engine | `permissions`, `roles`, `role_permissions`, `user_roles` |
| `audit` | Append-only audit events and query API | `audit_logs` |

Shared code: `app/core` (config, logging, redaction, errors, middleware, security
primitives), `app/db` (declarative base, naming conventions, engine/session),
`app/api` (dependencies, pagination, health, v1 router).

## API (`/api/v1`)

| Method & path | Permission | Notes |
| --- | --- | --- |
| `GET /health` | public | Liveness, no dependencies |
| `GET /ready` | public | Readiness, checks the database (503 if unavailable) |
| `POST /auth/login` | public | Sets session cookie; returns profile, permissions, CSRF token |
| `POST /auth/logout` | session + CSRF | Revokes the session server-side |
| `GET /auth/me` | session | Profile, company, roles, permissions, CSRF token |
| `POST /auth/change-password` | session + CSRF | Revokes other sessions |
| `GET /users` | `user.read` | Company-scoped grant lists everyone; narrower grants list self |
| `GET /users/{id}` | `user.read` | Includes role assignments |
| `POST /users/{id}/roles` | `role.manage` | Escalation guard, no self-assignment, audited |
| `DELETE /users/{id}/roles/{assignment_id}` | `role.manage` | Last Super Admin protected, audited |
| `GET /authz/permissions` | `role.read` | Catalogue |
| `GET /roles`, `GET /roles/{id}` | `role.read` | With permission keys and assignment counts |
| `GET /audit-logs` | `audit_log.read` (company scope) | Filters: action, actor, resource type, time range; paginated |

All errors use `{"error": {"code", "message", "details", "correlation_id"}}`.

## Frontend (`frontend/src`)

| Path | Purpose |
| --- | --- |
| `app/` | Providers, TanStack Query client (401 → sign-in), route table |
| `lib/api/client.js` | Fetch wrapper: credentials, CSRF header, error envelope → `ApiError` |
| `components/ui/` | Design-system primitives (button, input, card, alert, badge, loading/empty/error states) |
| `features/auth/` | Sign-in page, `useMe`/`usePermissions`, route guards, safe `?next=` redirects |
| `features/navigation/` | Permission-aware navigation (only delivered modules appear) |
| `features/dashboard/` | Overview: access summary, live platform status, honest empty state |
| `features/settings/` | Profile and password change |
| `features/admin/` | Read-only roles list and audit log |
| `layouts/AppLayout.jsx` | Collapsible sidebar, mobile drawer, header, skip link |

## Data rules in force

- UUID primary keys, UTC `timestamptz`, deterministic constraint names.
- Emails are stored lower-case (check constraint) and are unique per company.
- Session tokens are stored only as hashes; passwords as Argon2id hashes.
- Audit rows cannot be updated or deleted.
- Retention: `purge-auth-records` deletes login attempts older than 30 days and sessions
  more than 30 days past expiry or revocation. Schedule it on a Render cron job when
  workers are introduced.
