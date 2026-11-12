# ADR 0003 — Server-side sessions in HttpOnly cookies with CSRF tokens

**Status:** Accepted · **Date:** 2026-11-12

## Context

Staff sign in to a browser app. Tokens stored in `localStorage` are exposed to any XSS.
Sessions must be revocable (logout, password change, admin action) and work across
multiple API instances.

## Decision

- **Sessions:** random 256-bit token per sign-in; only its SHA-256 hash is stored in the
  `sessions` table. Idle timeout (`SESSION_IDLE_MINUTES`, default 60) and absolute expiry
  (`SESSION_ABSOLUTE_HOURS`, default 12). A new token is issued on every sign-in
  (prevents session fixation). Password change revokes all other sessions.
- **Cookie:** `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` outside local development.
  With no cookie domain configured, the name gets the `__Host-` prefix so browsers reject
  injected or subdomain-scoped copies.
- **CSRF:** the token is `HMAC(SECRET_KEY, session_token)`, returned by `/auth/login` and
  `/auth/me` and held in memory by the frontend. Every state-changing request must send it
  in `X-CSRF-Token`. An Origin allow-list check rejects cross-site unsafe requests as
  defence in depth.
- **Passwords:** Argon2id (argon2-cffi defaults, rehash on login when parameters change).
  Minimum 12 characters, maximum 128, no composition rules (NIST SP 800-63B).
- **Throttling:** failed attempts are stored in `login_attempts`; 5 failures per email or 20
  per IP within 15 minutes returns HTTP 429. Database-backed, so it holds across instances.
- **Enumeration:** unknown email, wrong password and disabled account return the same
  message; unknown accounts still run a dummy hash verification.

## Deployment constraint

Browsers treat `*.vercel.app` and `*.onrender.com` as different sites, so a cookie set by
the API would be a third-party cookie. Supported topologies:

1. **Custom subdomains (recommended):** e.g. `orbit.example.com` (Vercel) and
   `api.orbit.example.com` (Render). Same site, so `SameSite=Lax` cookies flow. Set
   `VITE_API_BASE_URL` to the API origin and add it to the CSP `connect-src`.
2. **Vercel rewrite proxy:** Vercel forwards `/api/*` to Render; the browser only talks to
   one origin. Leave `VITE_API_BASE_URL` empty.

## Consequences

- MFA (TOTP) for privileged accounts is a planned follow-up; the session model supports
  adding a second factor step without schema redesign.
- Self-service password reset by email waits for an email provider; operators use
  `python -m app.cli reset-password` meanwhile.
