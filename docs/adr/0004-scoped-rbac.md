# ADR 0004 — Scoped role-based access control

**Status:** Accepted · **Date:** 2026-11-12

## Context

The brief requires custom roles with resource/action/scope boundaries (company,
department, assigned product, assigned project, own records). Every API endpoint and every
future NOVA tool must enforce access on the server.

## Decision

- **Permissions** are `resource.action` keys defined in code
  (`app/modules/authorization/catalogue.py`) and synced to the `permissions` table.
  Actions: `read`, `create`, `update`, `delete`, `approve`, `export`, `manage`.
  Each permission carries an `is_sensitive` flag.
- **Roles** are company-owned and fully customisable. Thirteen starter roles are created by
  bootstrap. The **Super Admin** role is `is_locked`: it always holds every permission and
  cannot be edited. There is no `is_superuser` bypass flag; Super Admin access flows
  through the same permission checks as everyone else.
- **Assignments** (`user_roles`) grant a role at a scope: `company`, `department`,
  `product`, `project` (with `scope_id`) or `own`.
- **Policy** (`policy.py`) is pure and unit-tested:
  - `is_allowed(principal, permission, target=None)` with no target answers "may the user
    do this to some records?" (for example, opening a list). Queries must then be
    filtered to the user's scopes.
  - With a `ResourceContext`, a grant applies only if its scope covers the record.
- **Route guard:** `require_permission("x.y")` FastAPI dependency. Denials of sensitive
  permissions are audited.
- **Escalation guard:** to assign or revoke a role, the actor needs `role.manage` **and**
  must already hold every permission in that role at an equal or broader scope. Users
  cannot change their own role assignments. The last active Super Admin cannot be removed.
- Department, product and project scopes are rejected until the modules that own those
  records exist (`scope_not_available`). This prevents dangling scope IDs.

## Consequences

- Each new module must supply a `ResourceContext` for record-level checks and filter list
  queries by the principal's scopes.
- NOVA tools (Phase 6) reuse the same principal and policy; the model never gets a bypass.
- Custom roles (Phase 1 Core) follow the same rule: an editor can only create or change a
  role if they hold, company-wide, every permission the role holds before and after the edit.
- Product and department scopes are now validated (`app/modules/scopes.py`); project scope
  remains unavailable until the projects module exists.
