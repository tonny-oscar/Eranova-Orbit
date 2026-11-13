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
| `products` | Product registry, lifecycle history, team roster, product-scope validator | `products`, `product_members`, `product_status_history` |
| `people` | Departments, minimal employee work profiles, department-scope validator | `departments`, `employee_profiles` |
| `dashboard` | Live executive summary and global search (no tables; reads other modules) | — |
| `content` | Public website pages with draft and published copies | `content_pages` |
| `crm` | Leads and website enquiries (consent, attribution, spam limits) | `leads`, `enquiries` |
| `public` | Unauthenticated marketplace API (no tables; published data only) | — |

`app/modules/scopes.py` registers which module validates each role scope type
(product → `products`, department → `people`). Project scope stays unavailable until the
projects module exists.

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
| `GET /users` | `user.read` | Company grant: everyone; department grant: department members; always self. Includes role names |
| `POST /users` | `user.create` (company) | Returns a one-time temporary password; user must change it |
| `GET /users/{id}` | `user.read` | Includes role assignments and `can_update` / `can_manage` |
| `PATCH /users/{id}` | `user.update` (name), `user.manage` (status) | Disabling revokes sessions; cannot target self, more privileged accounts or the last Super Admin |
| `POST /users/{id}/reset-password` | `user.manage` | New temporary password; blocked for more privileged accounts |
| `POST /users/{id}/roles` | `role.manage` | Escalation guard, no self-assignment, audited |
| `DELETE /users/{id}/roles/{assignment_id}` | `role.manage` | Last Super Admin protected, audited |
| `GET /authz/permissions` | `role.read` | Catalogue |
| `GET /roles`, `GET /roles/{id}` | `role.read` | With permission keys and assignment counts |
| `POST /roles`, `PATCH /roles/{id}`, `DELETE /roles/{id}` | `role.create` / `role.update` / `role.delete` | Only permissions the editor holds company-wide; Super Admin locked; starter roles not deletable |
| `GET /audit-logs` | `audit_log.read` (company scope) | Filters: action, actor, resource type, time range; paginated |
| `GET /products` | `product.read` | Scope-filtered; search `q`, `status` |
| `POST /products` | `product.create` (company) | Creates status history entry, audited |
| `GET /products/{id}`, `PATCH /products/{id}` | `product.read` / `product.update` (record scope) | Returns `can_update` / `can_manage` |
| `POST /products/{id}/status` | `product.update` | Lifecycle change with reason, history and audit |
| `GET /products/{id}/status-history` | `product.read` | Newest first |
| `GET/POST/DELETE /products/{id}/members` | `product.read` / `product.manage` | Team roster (does not grant access) |
| `GET /employees`, `GET /employees/{user_id}` | `employee.read` | Company, department or own scope |
| `PUT /employees/{user_id}` | `employee.update` (current and target department) | Manager loop prevention, audited |
| `GET /departments` | `employee.read` | With head and member counts |
| `POST /departments`, `PATCH /departments/{id}` | `employee.manage` (company) | Audited |
| `POST /products/{id}/publish`, `/unpublish` | `product.approve` | Publish requires confirmed details, public status and a description |
| `GET /content/pages`, `GET /content/pages/{slug}` | `content.read` | Draft, published copy and unpublished-changes flag |
| `PUT /content/pages/{slug}` | `content.update` (company) | Saves draft only |
| `POST /content/pages/{slug}/publish`, `/unpublish` | `content.approve` (company) | Copies draft to live / takes page down |
| `GET /leads`, `GET /leads/{id}` | `lead.read` | Company, product or own scope; detail includes enquiry history |
| `PATCH /leads/{id}` | `lead.update` | Status, priority, owner, follow-up, notes; audited (notes text not logged) |
| `GET /public/site` | public | Company name, published pages, categories, privacy notice version |
| `GET /public/products`, `GET /public/products/{slug}` | public | Public products only; cached 60 s |
| `GET /public/pages/{slug}` | public | Published copy only |
| `POST /public/enquiries` | public | Creates/updates a lead; consent required; honeypot, timing and rate limits |
| `GET /dashboard/summary` | session | Sections included only when permitted; `generated_at` and `source` |
| `GET /search?q=` | session | Products and people within scope; min 2 characters |

All errors use `{"error": {"code", "message", "details", "correlation_id"}}`.

## Frontend (`frontend/src`)

| Path | Purpose |
| --- | --- |
| `app/` | Providers, TanStack Query client (401 → sign-in), route table |
| `lib/api/client.js` | Fetch wrapper: credentials, CSRF header, error envelope → `ApiError` |
| `components/ui/` | Design-system primitives (button, input, card, alert, badge, loading/empty/error states) |
| `features/auth/` | Sign-in page, `useMe`/`usePermissions`, route guards, safe `?next=` redirects |
| `features/navigation/` | Permission-aware navigation (only delivered modules appear) |
| `features/dashboard/` | Overview: live summary, access, platform status, explicit "not connected" notice |
| `features/products/` | Registry list, register/edit forms, detail with lifecycle, team and history |
| `features/team/` | People directory, departments, work profiles |
| `features/admin/` | Users (create, disable, reset, roles), role editor, audit log |
| `features/search/` | Header global search combobox |
| `features/public/` | Public marketplace: home, catalogue, product, pricing, CMS pages, enquiry forms, attribution capture |
| `features/website/` | Staff website editor (draft, publish) |
| `features/leads/` | Lead list and detail with enquiry history |
| `layouts/PublicLayout.jsx` | Public header, navigation and footer |
| `demo/` | In-memory API for `npm run dev:demo` (never in production builds) |
| `features/settings/` | Profile and password change (also the forced first-sign-in screen) |
| `layouts/AppLayout.jsx` | Collapsible sidebar, mobile drawer, header with search, skip link |

Authenticated pages are lazy-loaded so the public site and sign-in stay small.

## Data rules in force

- UUID primary keys, UTC `timestamptz`, deterministic constraint names.
- Emails are stored lower-case (check constraint) and are unique per company.
- Session tokens are stored only as hashes; passwords as Argon2id hashes.
- Audit rows cannot be updated or deleted. Audit and status-history rows carry per-row
  timestamps so events written in one transaction keep their order.
- Products and roles are never hard-deleted while referenced; product retirement is a
  lifecycle status. Employee profiles store work information only.
- Retention: `purge-auth-records` deletes login attempts older than 30 days and sessions
  more than 30 days past expiry or revocation. Schedule it on a Render cron job when
  workers are introduced.
