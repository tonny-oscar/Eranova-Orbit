import json
import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import correlation_id_var
from app.core.errors import error_body

logger = logging.getLogger("app.request")

CORRELATION_HEADER = "X-Correlation-ID"
_VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class RequestContextMiddleware:
    """Assigns a correlation ID, logs each request and adds baseline security headers."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(CORRELATION_HEADER, "")
        correlation_id = incoming if _VALID_CORRELATION_ID.match(incoming) else uuid.uuid4().hex
        correlation_id_var.set(correlation_id)
        scope.setdefault("state", {})["correlation_id"] = correlation_id

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[CORRELATION_HEADER] = correlation_id
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.setdefault("Cache-Control", "no-store")
                if self.hsts:
                    headers.setdefault(
                        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )


class OriginCheckMiddleware:
    """Rejects state-changing requests whose Origin header is not an allowed origin.

    Defence in depth alongside SameSite cookies and the CSRF token. Requests
    without an Origin header (server-to-server, CLI tools) pass through; they
    cannot carry a browser session cookie set as SameSite from another site.
    """

    def __init__(self, app: ASGIApp, *, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed = {origin.rstrip("/") for origin in allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in _UNSAFE_METHODS:
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            if (
                origin
                and origin.rstrip("/") not in self.allowed
                and not self._same_host(origin, headers.get("host"))
            ):
                body = json.dumps(
                    error_body("origin_not_allowed", "Request origin is not allowed.")
                ).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)

    @staticmethod
    def _same_host(origin: str, host: str | None) -> bool:
        if not host:
            return False
        return origin.split("://", 1)[-1].rstrip("/") == host
