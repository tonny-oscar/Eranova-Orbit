# ADR 0002 — Async SQLAlchemy with asyncpg

**Status:** Accepted · **Date:** 2026-11-12

## Context

Orbit will make many I/O-bound calls (product APIs, GitHub, Vercel, analytics, AI
providers, streaming NOVA responses). The owner develops on Windows.

## Options

1. Synchronous SQLAlchemy with psycopg (FastAPI thread pool).
2. Async SQLAlchemy with psycopg 3 async.
3. Async SQLAlchemy with asyncpg.

## Decision

Option 3. psycopg's async mode cannot run on Windows' default `ProactorEventLoop`, which
uvicorn uses, so it would break local development. asyncpg works on all platforms.

`DATABASE_URL` values in libpq form (`postgresql://…?sslmode=require`, as Render provides)
are normalised to `postgresql+asyncpg://…?ssl=require` in `app/core/config.py`.

## Consequences

- No lazy loading on ORM relationships: queries load what they need explicitly.
- Alembic runs through an async engine; tests pass an existing connection to Alembic.
- Tests use real PostgreSQL (never SQLite) so constraints and triggers are exercised.
