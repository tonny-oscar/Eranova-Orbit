import hashlib
import hmac
import json
import re

from app.integrations.base import (
    Adapter,
    ConfigField,
    HealthResult,
    Record,
    SyncResult,
    WebhookResult,
)
from app.integrations.http import IntegrationError, client, raise_for_status

API = "https://api.github.com"
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class GitHubAdapter(Adapter):
    provider = "github"
    label = "GitHub repository"
    description = "Repository health, open pull requests and issues; links PRs to Orbit tasks."
    capabilities = ("health_check", "sync_incremental", "receive_webhook", "task_linking")
    config_fields = (
        ConfigField("owner", "Owner or organisation", help="e.g. eranova"),
        ConfigField("repo", "Repository name", help="e.g. shulepoa"),
    )
    secret_help = "Fine-grained token with read-only access to metadata, issues and pull requests."
    supports_webhooks = True

    @classmethod
    def validate_config(cls, config):
        owner, repo = str(config.get("owner", "")).strip(), str(config.get("repo", "")).strip()
        if not (_NAME.match(owner) and _NAME.match(repo)):
            raise IntegrationError("Enter a valid GitHub owner and repository name.")
        return {"owner": owner, "repo": repo}

    @property
    def full_name(self) -> str:
        return f"{self.config['owner']}/{self.config['repo']}"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.secret:
            headers["Authorization"] = f"Bearer {self.secret}"
        return headers

    async def health_check(self) -> HealthResult:
        async with client() as http:
            response = await http.get(f"{API}/repos/{self.full_name}", headers=self._headers())
        raise_for_status(response, "GitHub")
        repo = response.json()
        return HealthResult(
            True, f"Connected to {repo.get('full_name')}", {"private": repo.get("private")}
        )

    async def sync(self) -> SyncResult:
        async with client() as http:
            repo_r = await http.get(f"{API}/repos/{self.full_name}", headers=self._headers())
            raise_for_status(repo_r, "GitHub")
            pulls_r = await http.get(
                f"{API}/repos/{self.full_name}/pulls",
                params={"state": "open", "per_page": 30},
                headers=self._headers(),
            )
            raise_for_status(pulls_r, "GitHub")
        repo = repo_r.json()
        records = [
            Record(
                "repository",
                self.full_name,
                {
                    "full_name": repo.get("full_name"),
                    "url": repo.get("html_url"),
                    "default_branch": repo.get("default_branch"),
                    "open_issues": repo.get("open_issues_count"),
                    "pushed_at": repo.get("pushed_at"),
                    "visibility": repo.get("visibility"),
                },
            )
        ]
        for pr in pulls_r.json():
            records.append(
                Record(
                    "pull_request",
                    f"{self.full_name}#{pr.get('number')}",
                    {
                        "number": pr.get("number"),
                        "title": (pr.get("title") or "")[:200],
                        "url": pr.get("html_url"),
                        "author": (pr.get("user") or {}).get("login"),
                        "draft": pr.get("draft"),
                        "updated_at": pr.get("updated_at"),
                    },
                )
            )
        return SyncResult(records, {"open_pull_requests": len(records) - 1})

    def verify_webhook(self, headers, body) -> bool:
        signature = headers.get("x-hub-signature-256", "")
        if not self.webhook_secret or not signature.startswith("sha256="):
            return False
        expected = hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature[7:], expected)

    def parse_webhook(self, headers, body) -> WebhookResult:
        event = headers.get("x-github-event", "unknown")
        delivery = headers.get("x-github-delivery", "")
        payload = json.loads(body or b"{}")
        result = WebhookResult(event, delivery, {"action": payload.get("action")})
        pr = payload.get("pull_request")
        if event == "pull_request" and pr:
            ref = f"{self.full_name}#{pr.get('number')}"
            result.summary.update({"pr": ref, "merged": pr.get("merged")})
            result.records.append(
                Record(
                    "pull_request",
                    ref,
                    {
                        "number": pr.get("number"),
                        "title": (pr.get("title") or "")[:200],
                        "url": pr.get("html_url"),
                        "state": pr.get("state"),
                        "merged": pr.get("merged"),
                        "updated_at": pr.get("updated_at"),
                    },
                )
            )
            result.task_evidence.append(
                (
                    ref,
                    pr.get("html_url") or "",
                    f"PR #{pr.get('number')} {payload.get('action')}",
                    "github_pr",
                )
            )
        return result
