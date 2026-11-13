import hashlib
import hmac
import json
import re
from datetime import UTC, datetime

from app.integrations.base import (
    Adapter,
    ConfigField,
    HealthResult,
    Record,
    SyncResult,
    WebhookResult,
)
from app.integrations.http import IntegrationError, client, raise_for_status

API = "https://api.vercel.com"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


class VercelAdapter(Adapter):
    provider = "vercel"
    label = "Vercel project"
    description = "Deployment status and history for a Vercel project."
    capabilities = ("health_check", "sync_incremental", "get_service_status", "receive_webhook")
    config_fields = (
        ConfigField("project_id", "Project ID or name"),
        ConfigField("team_id", "Team ID", required=False, help="Only for team-owned projects."),
    )
    secret_required = True
    secret_help = "Vercel access token scoped to the team, read access is enough."
    supports_webhooks = True

    @classmethod
    def validate_config(cls, config):
        project = str(config.get("project_id", "")).strip()
        team = str(config.get("team_id") or "").strip()
        if not _ID.match(project) or (team and not _ID.match(team)):
            raise IntegrationError("Enter a valid Vercel project (and team) ID.")
        return {"project_id": project, "team_id": team or None}

    def _params(self, extra=None) -> dict:
        params = dict(extra or {})
        if self.config.get("team_id"):
            params["teamId"] = self.config["team_id"]
        return params

    def _headers(self):
        return {"Authorization": f"Bearer {self.secret}"}

    async def health_check(self) -> HealthResult:
        async with client() as http:
            response = await http.get(
                f"{API}/v9/projects/{self.config['project_id']}",
                params=self._params(),
                headers=self._headers(),
            )
        raise_for_status(response, "Vercel")
        project = response.json()
        return HealthResult(
            True, f"Connected to {project.get('name')}", {"framework": project.get("framework")}
        )

    async def sync(self) -> SyncResult:
        async with client() as http:
            response = await http.get(
                f"{API}/v6/deployments",
                params=self._params({"projectId": self.config["project_id"], "limit": 10}),
                headers=self._headers(),
            )
        raise_for_status(response, "Vercel")
        records = []
        for d in response.json().get("deployments", []):
            created = d.get("created") or d.get("createdAt")
            records.append(
                Record(
                    "deployment",
                    str(d.get("uid")),
                    {
                        "state": d.get("state") or d.get("readyState"),
                        "target": d.get("target") or "preview",
                        "url": f"https://{d['url']}" if d.get("url") else None,
                        "branch": (d.get("meta") or {}).get("githubCommitRef"),
                        "commit": ((d.get("meta") or {}).get("githubCommitMessage") or "")[:200],
                        "created_at": datetime.fromtimestamp(created / 1000, UTC).isoformat()
                        if created
                        else None,
                    },
                )
            )
        latest_production = next((r for r in records if r.data["target"] == "production"), None)
        return SyncResult(
            records,
            {
                "deployments": len(records),
                "latest_production_state": latest_production.data["state"]
                if latest_production
                else None,
            },
        )

    def verify_webhook(self, headers, body) -> bool:
        signature = headers.get("x-vercel-signature", "")
        if not self.webhook_secret or not signature:
            return False
        expected = hmac.new(self.webhook_secret.encode(), body, hashlib.sha1).hexdigest()
        return hmac.compare_digest(signature, expected)

    def parse_webhook(self, headers, body) -> WebhookResult:
        payload = json.loads(body or b"{}")
        deployment = (payload.get("payload") or {}).get("deployment") or {}
        result = WebhookResult(
            payload.get("type", "unknown"),
            str(payload.get("id", "")),
            {"type": payload.get("type")},
        )
        if deployment.get("id"):
            result.records.append(
                Record(
                    "deployment",
                    str(deployment["id"]),
                    {
                        "state": payload.get("type", "").replace("deployment.", ""),
                        "url": f"https://{deployment['url']}" if deployment.get("url") else None,
                        "target": (payload.get("payload") or {}).get("target") or "preview",
                    },
                )
            )
        return result
