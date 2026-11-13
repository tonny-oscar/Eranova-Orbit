# ADR 0011 — Integrations, secret references and the worker

**Status:** Accepted · **Date:** 2026-11-13

## Context

Eranova's live products (CRM, ShulePoa and others) run in their own repositories and
deployments. Orbit must show their health and figures without copying customer data,
storing credentials in its database, or becoming a route into internal networks.

## Decision

- Each provider is an adapter (`app/integrations/*`) with `health_check`, `sync`,
  `verify_webhook` and `parse_webhook`. Products implement the small read-only contract in
  `docs/integrations/product-api-contract.md`.
- Connections store only the **name** of an environment variable (`INTEGRATION_*`). The
  value is read at call time. Other server secrets cannot be referenced.
- Outbound calls resolve DNS first and refuse private, loopback and link-local addresses;
  HTTPS is required outside local development.
- Webhooks are HMAC-verified (with a replay window for product webhooks) and de-duplicated by
  delivery id. Rejections are audited.
- Records keep minimal normalised facts (aggregate metrics, deployment state, PR titles).
  Every view shows the source and last successful sync; failures stay visible.
- A single background worker (`python -m app.worker`) runs scheduled syncs, reminders,
  scheduled reports and retention. All state is in PostgreSQL, so restarts are safe.

## Consequences

- Rotating a credential is an environment change, not a database edit.
- Run exactly one worker instance; jobs are idempotent but not designed for concurrency.
