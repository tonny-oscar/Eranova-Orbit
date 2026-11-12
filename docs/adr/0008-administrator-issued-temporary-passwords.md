# ADR 0008 — Administrator-issued temporary passwords

**Status:** Accepted · **Date:** 2026-11-13

## Context

There is no email provider yet, so invitations and self-service reset are not possible.
Administrators still need to onboard staff and help people who are locked out, without
choosing or knowing long-term passwords.

## Decision

- Creating a user or resetting a password generates a random 16-character temporary
  password server-side. It is returned **once** in the response (`Cache-Control: no-store`)
  and never logged or stored in plaintext.
- `users.must_change_password` is set. Until the user changes it, the API only permits
  `/auth/me`, `/auth/logout` and `/auth/change-password` (`password_change_required`),
  and the UI shows a forced "Set your password" screen.
- Resetting or disabling an account revokes all of its sessions.
- An administrator may only reset, disable or enable an account if they hold, company-wide,
  every permission that account holds. This prevents a delegated helpdesk admin from taking
  over a Super Admin. Self-administration and disabling the last active Super Admin are
  blocked. Denied attempts are audited.

## Consequences

- Temporary passwords must be shared through a private channel; replace this with email
  invitations and self-service reset when an email provider is approved.
