"""Google Analytics 4 Data API using a service account (read-only)."""

import base64
import json
import re
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.integrations.base import Adapter, ConfigField, HealthResult, Record, SyncResult
from app.integrations.http import IntegrationError, client, raise_for_status

TOKEN_URL = "https://oauth2.googleapis.com/token"
DATA_API = "https://analyticsdata.googleapis.com/v1beta"
SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class GA4Adapter(Adapter):
    provider = "ga4"
    label = "Google Analytics 4"
    description = "Daily visitors, sessions, page views and conversions for a product website."
    capabilities = ("health_check", "get_usage_metrics", "sync_incremental")
    config_fields = (
        ConfigField("property_id", "GA4 property ID", help="Numbers only, e.g. 412345678"),
    )
    secret_required = True
    secret_help = (
        "Service account JSON key with Viewer access to the property (store the whole JSON)."
    )

    @classmethod
    def validate_config(cls, config):
        property_id = str(config.get("property_id", "")).strip()
        if not re.fullmatch(r"\d{4,20}", property_id):
            raise IntegrationError("The GA4 property ID is a number, e.g. 412345678.")
        return {"property_id": property_id}

    async def _token(self, http) -> str:
        try:
            account = json.loads(self.secret or "")
            key = serialization.load_pem_private_key(account["private_key"].encode(), password=None)
        except (ValueError, KeyError, TypeError) as exc:
            raise IntegrationError("The service account secret is not a valid JSON key.") from exc
        now = int(time.time())
        header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        claims = _b64(
            json.dumps(
                {
                    "iss": account["client_email"],
                    "scope": SCOPE,
                    "aud": TOKEN_URL,
                    "iat": now,
                    "exp": now + 3600,
                }
            ).encode()
        )
        signature = key.sign(f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
        response = await http.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": f"{header}.{claims}.{_b64(signature)}",
            },
        )
        raise_for_status(response, "Google")
        return response.json()["access_token"]

    async def _report(self, days: int) -> dict:
        async with client() as http:
            token = await self._token(http)
            response = await http.post(
                f"{DATA_API}/properties/{self.config['property_id']}:runReport",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "yesterday"}],
                    "dimensions": [{"name": "date"}],
                    "metrics": [
                        {"name": "activeUsers"},
                        {"name": "sessions"},
                        {"name": "screenPageViews"},
                        {"name": "conversions"},
                    ],
                },
            )
        raise_for_status(response, "Google Analytics")
        return response.json()

    async def health_check(self) -> HealthResult:
        report = await self._report(1)
        return HealthResult(
            True, "Connected to Google Analytics", {"rows": report.get("rowCount", 0)}
        )

    async def sync(self) -> SyncResult:
        report = await self._report(28)
        names = [m["name"] for m in report.get("metricHeaders", [])]
        records = []
        for row in report.get("rows", []):
            day = row["dimensionValues"][0]["value"]
            values = {
                n: float(v["value"]) for n, v in zip(names, row["metricValues"], strict=False)
            }
            records.append(
                Record("traffic_daily", day, {"date": f"{day[:4]}-{day[4:6]}-{day[6:]}", **values})
            )
        return SyncResult(records, {"days": len(records)})
