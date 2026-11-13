# ADR 0012 — Document files stored in PostgreSQL

**Status:** Accepted · **Date:** 2026-11-13

## Context

The document centre needs durable file storage with the same permission checks as the
records it belongs to. The deployment (Render web service + managed PostgreSQL) has no
persistent disk, and adding object storage means another account, credentials and backup
process.

## Decision

- File bytes live in `document_blobs` (one row per version), separate from document
  metadata so listings never load contents.
- Limit 10 MB per file; an allow-list of office, PDF, image and plain-text types. The type is
  derived from the extension **and** verified against the file signature; the client's
  declared type is ignored. HTML, SVG, scripts and archives are rejected.
- Downloads are always `Content-Disposition: attachment` with `nosniff`, a sandboxing CSP and
  `no-store`, and every download is audited.
- Access combines the reader's `document.read` scope (company, department, product, project
  or own) with optional restriction to the owner and named members. The same rule is used
  for listing, search, detail and download.

## Consequences

- Files are included in database backups and point-in-time recovery automatically.
- Database size grows with documents; revisit (move blobs to S3-compatible storage behind
  the same service functions) if total storage approaches the plan limit.
