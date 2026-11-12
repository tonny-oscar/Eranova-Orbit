# ADR 0005 — Append-only audit log

**Status:** Accepted · **Date:** 2026-11-12

## Context

Privileged actions, approvals, permission changes, exports and integration changes must
be auditable, and the trail must not be silently editable.

## Decision

- Table `audit_logs` records: actor type (`user`, `system`, `nova`, `anonymous`), actor
  user, action (e.g. `role.assignment.create`), resource type and ID, outcome
  (`success`, `failure`, `denied`), IP, user agent, correlation ID and a JSON `details`
  object.
- `details` is passed through the redaction helper (keys like `password`, `token`,
  `secret` and `api_key` are masked) before it is stored.
- A PostgreSQL trigger rejects `UPDATE`, `DELETE` and `TRUNCATE` on the table. Foreign keys
  from audit rows use `ON DELETE RESTRICT`, so audited users cannot be hard-deleted.
- Audit events are written in the same transaction as the change they describe. Denied
  and failed attempts are committed before the error response is returned.

## Events recorded in Phase 1

`auth.login.succeeded`, `auth.login.failed`, `auth.login.throttled`, `auth.logout`,
`auth.password.changed`, `auth.password.change_failed`, `auth.password.reset`,
`authz.denied` (sensitive permissions), `role.assignment.create`,
`role.assignment.delete` (including denied escalation attempts), `user.create` (CLI).

## Consequences

- Retention will need an archival process that runs as a privileged database role. The
  application role must never get rights to bypass the trigger.
- In production the application should connect as a role without `TRIGGER`/DDL rights
  (Phase 8 hardening).
