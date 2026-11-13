# ADR 0010 — Frontend demo preview mode

**Status:** Accepted · **Date:** 2026-11-13

## Context

The owner needs to see and review screens before a local database is available, without
removing or weakening authentication in the real application.

## Decision

- `npm run dev:demo` starts Vite in mode `demo`. In that mode only, `apiRequest` routes
  calls to an in-memory API (`src/demo/demoApi.js`) instead of the backend.
- The demo signs you in as a demo Super Admin; any credentials work after signing out.
- Data is sample data. The five launch products stay unconfirmed drafts with no invented
  details. One clearly fictional "Sample App (demo)" product, a sample page and a sample
  lead exist so the public site and lead screens can be previewed.
- A permanent banner states that sign-in is disabled and the data is sample data.
- `DEMO_MODE` is `import.meta.env.DEV && MODE === 'demo'`, a build-time constant.
  Production builds tree-shake the demo code entirely; this is checked by searching the
  build output for demo strings.

## Consequences

- New screens must add matching demo routes to stay viewable in the preview.
- The backend's authentication and authorization are unchanged and remain the security
  boundary.
