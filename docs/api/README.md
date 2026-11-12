# API reference

The FastAPI application generates its OpenAPI schema automatically.

- Local: http://localhost:8000/docs (Swagger UI) and http://localhost:8000/openapi.json
- Staging: `https://<staging-api-host>/docs`
- Production: disabled (`ENVIRONMENT=production` turns off `/docs` and `/openapi.json`).

An endpoint summary with required permissions is maintained in
[`docs/architecture/overview.md`](../architecture/overview.md#api-apiv1).

## Conventions

- All business endpoints are versioned under `/api/v1`.
- Authentication: session cookie set by `POST /api/v1/auth/login`.
- State-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) require the `X-CSRF-Token`
  header with the value returned by `/auth/login` or `/auth/me`.
- Every response includes `X-Correlation-ID`. Send your own (8–64 characters
  `[A-Za-z0-9._-]`) to trace a request across services.
- Lists are paginated with `limit` (1–100, default 25) and `offset`, and return
  `{items, total, limit, offset}`.
- Errors: `{"error": {"code": "...", "message": "...", "details": [...], "correlation_id": "..."}}`.
  Validation errors never echo submitted values.
