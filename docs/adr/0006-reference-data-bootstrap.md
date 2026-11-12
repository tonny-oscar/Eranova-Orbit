# ADR 0006 — Reference data via idempotent bootstrap

**Status:** Accepted · **Date:** 2026-11-12

## Context

The company record, the permission catalogue and the starter roles must exist in every
environment. Alembic must own all **schema** changes, but hard-coding reference data
inside migrations freezes it at one point in time and makes catalogue changes awkward.

## Decision

`python -m app.cli bootstrap` (run in Render's pre-deploy step after
`alembic upgrade head`) idempotently:

1. ensures the company row (from `COMPANY_NAME` / `COMPANY_SLUG`);
2. upserts the permission catalogue from code (stale keys are logged, not deleted);
3. creates any missing starter roles with their default permissions;
4. keeps the locked Super Admin role in sync with the full catalogue.

Administrator customisations of non-locked starter roles are never overwritten.

No demo users, sample metrics or fixtures are created. The first Super Admin is created
interactively with `create-superadmin`. Credentials never appear in environment
variables or command arguments.

## Consequences

- Adding a permission is a code change plus a deploy; Super Admin picks it up
  automatically, while other roles get it only when an administrator grants it.
