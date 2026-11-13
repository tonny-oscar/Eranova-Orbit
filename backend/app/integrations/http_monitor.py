import asyncio
import socket
import ssl
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit

from app.integrations.base import Adapter, ConfigField, HealthResult, Record, SyncResult
from app.integrations.http import IntegrationError, client, ensure_safe_url


def _certificate_expiry(host: str, port: int) -> str | None:
    context = ssl.create_default_context()
    with (
        socket.create_connection((host, port), timeout=5) as sock,
        context.wrap_socket(sock, server_hostname=host) as tls,
    ):
        not_after = tls.getpeercert().get("notAfter")
    if not not_after:
        return None
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), UTC).isoformat()


class HttpMonitorAdapter(Adapter):
    """Technical monitoring (uptime, latency, TLS expiry), separate from marketing analytics."""

    provider = "http_monitor"
    label = "Uptime monitor"
    description = "Checks a URL responds, measures latency and watches TLS certificate expiry."
    capabilities = ("health_check", "get_service_status")
    config_fields = (
        ConfigField("url", "URL to check", kind="url", help="e.g. https://shulepoa.co.ke/health"),
        ConfigField("expected_status", "Expected HTTP status", required=False, kind="number"),
    )

    @classmethod
    def validate_config(cls, config):
        url = ensure_safe_url(str(config.get("url", "")).strip())
        expected = int(config.get("expected_status") or 200)
        if not 100 <= expected <= 599:
            raise IntegrationError("Expected status must be a valid HTTP status code.")
        return {"url": url, "expected_status": expected}

    async def _check(self) -> Record:
        url = ensure_safe_url(self.config["url"])
        started = time.perf_counter()
        status, error = None, None
        try:
            async with client() as http:
                response = await http.get(url)
            status = response.status_code
        except Exception as exc:
            error = type(exc).__name__
        latency_ms = round((time.perf_counter() - started) * 1000)
        cert_expiry = None
        parts = urlsplit(url)
        if parts.scheme == "https" and status is not None:
            try:
                cert_expiry = await asyncio.to_thread(
                    _certificate_expiry, parts.hostname, parts.port or 443
                )
            except (OSError, ssl.SSLError):
                cert_expiry = None
        up = status == self.config.get("expected_status", 200)
        checked_at = datetime.now(UTC)
        return Record(
            "uptime_check",
            checked_at.strftime("%Y%m%d%H%M"),
            {
                "up": up,
                "status": status,
                "latency_ms": latency_ms,
                "error": error,
                "certificate_expires_at": cert_expiry,
            },
            observed_at=checked_at,
        )

    async def health_check(self) -> HealthResult:
        record = await self._check()
        message = (
            f"Up ({record.data['status']}, {record.data['latency_ms']} ms)"
            if record.data["up"]
            else f"Down ({record.data['status'] or record.data['error']})"
        )
        return HealthResult(record.data["up"], message, record.data)

    async def sync(self) -> SyncResult:
        record = await self._check()
        return SyncResult(
            [record], {"up": record.data["up"], "latency_ms": record.data["latency_ms"]}
        )
