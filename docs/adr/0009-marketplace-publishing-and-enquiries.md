# ADR 0009 — Marketplace publishing and enquiry handling

**Status:** Accepted · **Date:** 2026-11-13

## Context

The public marketplace must show product information without inventing facts, let staff
update content without code changes, and turn enquiries into CRM leads with consent,
source attribution and spam protection. It also falls under the Kenya Data Protection
Act.

## Decision

**Publishing**
- A product is public only when *all* of these hold: `is_published`, `details_confirmed`,
  lifecycle status beta/live/maintenance. The publish endpoint also requires a description.
  Unconfirming a product or moving it out of those statuses hides it immediately, with no
  extra step.
- Publishing uses the `product.approve` permission (Super Admin and Executive by default).
  Product managers can edit but not publish.
- The public API returns dedicated `PublicProduct` / `PublicPage` schemas. Internal
  fields (IDs, owners, repositories, deployment and analytics references) never leave
  the server.

**Website content**
- Nine known pages (`home`, `solutions`, `pricing`, `resources`, `about`, `careers`,
  `contact`, `support`, `privacy`). Each has a draft and a separately published copy, so
  editing never changes the live site until someone publishes.
- New permission resource `content` (`read`, `update`, `approve`). Marketing can draft;
  publishing needs `content.approve`.
- Content is plain text sections rendered as text, never HTML, so it can't introduce XSS.
- Unpublished pages show an honest "being prepared" placeholder rather than filler copy.

**Enquiries → leads**
- `POST /public/enquiries` creates or updates a lead keyed by (email, product). Each
  submission is kept as an `enquiries` row with the message, consent flags, privacy-notice
  version, UTM tags, referrer and landing page.
- Privacy-notice consent is mandatory. Marketing consent is optional and the latest
  choice wins.
- Spam protection: a hidden honeypot field, a minimum time on the form (3 s), and
  database-backed rate limits (5 per IP per 10 min, 3 per email per hour). Suspected bots
  receive the normal success response but nothing is stored, so the filter can't be probed.
- The IP is stored only as a salted SHA-256 hash, for throttling.
- Only published products can be referenced by an enquiry; anything else is ignored.

## Consequences

- A CAPTCHA (e.g. Cloudflare Turnstile) can be added later if abuse appears, and staff
  notifications for new leads need the notifications module.
- The privacy notice text must be written and legally reviewed, then published through
  the website editor. `PRIVACY_NOTICE_VERSION` must be bumped whenever the notice changes.
- Lead pipelines, activities, conversion to customers and deduplication across products
  are Phase 3 (CRM).
