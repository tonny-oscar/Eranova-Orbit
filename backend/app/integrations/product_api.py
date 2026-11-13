"""Generic adapter for Eranova's own live products (ShulePoa, HostPilot, your CRM, ...).

Each product exposes a small, read-only "Orbit integration" API described in
docs/integrations/product-api-contract.md. Orbit stores only aggregate
figures, never copies of the product's customer records.
"""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from numbers import Number

from app.integrations.base import (
    Adapter,
    ConfigField,
    HealthResult,
    Record,
    SyncResult,
    WebhookResult,
)
from app.integrations.http import IntegrationError, client, ensure_safe_url, raise_for_status

MAX_METRICS = 50
REPLAY_WINDOW_SECONDS = 300


def _clean_path(path: str | None, default: str | None) -> str | None:
    path = (path or default or "").strip()
    if not path:
        return None
    if not path.startswith("/") or ".." in path or "//" in path:
        raise IntegrationError("Paths must start with / and stay on the product's own host.")
    return path


class ProductApiAdapter(Adapter):
    provider = "product_api"
    label = "Eranova product API"
    description = "Connects a live Eranova product (CRM, ShulePoa, ...) via its Orbit endpoints."
    capabilities = ("health_check", "get_service_status", "get_usage_metrics", "receive_webhook")
    config_fields = (
        ConfigField(
            "base_url", "Product API base URL", kind="url", help="e.g. https://api.shulepoa.co.ke"
        ),
        ConfigField("health_path", "Health path", required=False, help="Default /orbit/health"),
        ConfigField("metrics_path", "Metrics path", required=False, help="Default /orbit/metrics"),
    )
    secret_required = True
    secret_help = "API key the product issues to Orbit (read-only)."
    supports_webhooks = True

    @classmethod
    def validate_config(cls, config):
        base_url = ensure_safe_url(str(config.get("base_url", "")).strip().rstrip("/"))
        return {
            "base_url": base_url,
            "health_path": _clean_path(config.get("health_path"), "/orbit/health"),
            "metrics_path": _clean_path(config.get("metrics_path"), "/orbit/metrics"),
        }

    def _headers(self):
        return {"Authorization": f"Bearer {self.secret}", "Accept": "application/json"}

    def _url(self, path: str) -> str:
        return ensure_safe_url(self.config["base_url"] + path)

    async def health_check(self) -> HealthResult:
        async with client() as http:
            response = await http.get(
                self._url(self.config["health_path"]), headers=self._headers()
            )
        raise_for_status(response, "Product API")
        body = response.json() if "json" in response.headers.get("content-type", "") else {}
        status = str(body.get("status", "ok"))
        return HealthResult(
            status in ("ok", "healthy", "pass"),
            f"Product reports '{status}'",
            {
                "version": body.get("version"),
            },
        )

    async def sync(self) -> SyncResult:
        if not self.config.get("metrics_path"):
            return SyncResult([], {"metrics": 0})
        async with client() as http:
            response = await http.get(
                self._url(self.config["metrics_path"]), headers=self._headers()
            )
        raise_for_status(response, "Product API")
        try:
            body = response.json()
        except ValueError as exc:
            raise IntegrationError("The product's metrics endpoint did not return JSON.") from exc
        raw = body.get("metrics", body) if isinstance(body, dict) else {}
        metrics = {
            str(k)[:60]: v
            for k, v in list(raw.items())[:MAX_METRICS]
            if isinstance(v, Number) and not isinstance(v, bool)
        }
        observed = datetime.now(UTC)
        period = (
            str(body.get("period", observed.strftime("%Y-%m-%d")))[:20]
            if isinstance(body, dict)
            else ""
        )
        return SyncResult(
            [
                Record(
                    "product_metrics",
                    period or observed.isoformat(),
                    {
                        "metrics": metrics,
                        "period": period,
                        "as_of": body.get("as_of") if isinstance(body, dict) else None,
                    },
                    observed_at=observed,
                )
            ],
            {"metrics": len(metrics)},
        )

    def verify_webhook(self, headers, body) -> bool:
        """HMAC-SHA256 over "<timestamp>.<body>" with a 5-minute replay window."""
        signature = headers.get("x-orbit-signature", "")
        timestamp = headers.get("x-orbit-timestamp", "")
        if not (self.webhook_secret and signature and timestamp.isdigit()):
            return False
        if abs(time.time() - int(timestamp)) > REPLAY_WINDOW_SECONDS:
            return False
        expected = hmac.new(
            self.webhook_secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    def parse_webhook(self, headers, body) -> WebhookResult:
        payload = json.loads(body or b"{}")
        return WebhookResult(
            str(payload.get("type", "event"))[:60],
            str(headers.get("x-orbit-delivery") or payload.get("id") or ""),
            {"type": payload.get("type")},
        )
