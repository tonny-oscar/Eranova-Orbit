# ADR 0001 — Repository layout and modular monolith

**Status:** Accepted · **Date:** 2026-11-12

## Context

Orbit needs a React frontend (Vercel) and a FastAPI backend (Render). Each Eranova product
keeps its own repository and database; Orbit must not become a monorepo of products.

## Options

1. Separate repositories for Orbit frontend and backend.
2. One Orbit repository containing `frontend/` and `backend/`.
3. Microservices from day one.

## Decision

Option 2. One `eranova-orbit` repository with `frontend/` and `backend/`, deployed
independently (Vercel root `frontend/`, Render root `backend/`). The backend is a
**modular monolith**: each domain lives in `backend/app/modules/<domain>/` with its own
`models.py`, `schemas.py`, `service.py` and `router.py`. Shared infrastructure lives in
`app/core`, `app/db` and `app/api`.

This adapts the brief's suggested structure (top-level `models/`, `services/`) to a
per-domain layout so each module's boundaries stay visible as the platform grows.

## Consequences

- Frontend and backend changes for one feature can ship in one reviewed pull request.
- Product repositories are untouched; integrations use adapters (later phases).
- Modules may be extracted into services later if load or team boundaries justify it.
- Route handlers stay thin; business rules live in services and are unit-testable.
