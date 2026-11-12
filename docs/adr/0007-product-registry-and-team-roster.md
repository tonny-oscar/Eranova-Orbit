# ADR 0007 — Product registry, team roster and product-scoped access

**Status:** Accepted · **Date:** 2026-11-13

## Context

Products must be registered without redesigning Orbit's core, each keeps its own
repository and database, and the brief forbids inventing product facts. People also need
product-level access boundaries.

## Decision

- `products` stores registry metadata only (links, ownership, lifecycle, pricing
  metadata, analytics source). Integration capabilities and connections arrive in
  Phase 4 as separate tables.
- `details_confirmed` defaults to false. The UI labels unconfirmed products
  "Awaiting confirmation" until a product owner confirms them. The launch products
  are registered by `register-initial-products` with names only.
- Lifecycle changes go through a dedicated endpoint that writes
  `product_status_history` and an audit event. Products are retired, not deleted.
- `product_members` is the team roster, which is informational. **Access** comes only from
  role assignments with `scope_type = product`. Keeping the two separate means adding
  someone to a team page can never silently grant permissions.
- `products.service` registers `product_exists` as the product-scope validator.

## Consequences

- Granting a product team access is two explicit steps (roster and role), each audited.
- Future product-specific modules (CRM, projects, analytics) reuse `product_id` and the
  same scope filter helper.
