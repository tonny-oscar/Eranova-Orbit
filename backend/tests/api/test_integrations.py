import hashlib
import hmac
import json
import time

import httpx
import pytest
from sqlalchemy import select

from app.integrations import http as integration_http
from app.modules.audit.models import AuditLog
from app.modules.integrations.models import IntegrationRecord, SyncRun
from app.modules.work.models import TaskEvent
from tests.conftest import login


def _routes(handlers):
    def handler(request: httpx.Request) -> httpx.Response:
        for (method, prefix), fn in handlers.items():
            if request.method == method and str(request.url).startswith(prefix):
                return fn(request)
        return httpx.Response(404, json={"message": "not mocked"})

    return httpx.MockTransport(handler)


@pytest.fixture
def external(monkeypatch):
    """Mock outbound HTTP and DNS so tests never touch the network."""
    monkeypatch.setattr(integration_http, "resolve_host", lambda host: ["93.184.216.34"])
    holder = {}

    def install(handlers):
        integration_http.set_transport(_routes(handlers))
        holder["installed"] = True

    yield install
    integration_http.set_transport(None)


async def _admin(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    return {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}


async def test_providers_catalogue(client, make_user):
    await _admin(client, make_user)
    providers = {p["provider"] for p in (await client.get("/api/v1/integrations/providers")).json()}
    assert providers == {"product_api", "github", "vercel", "ga4", "http_monitor"}


async def test_secret_refs_must_be_integration_scoped(client, make_user, external):
    h = await _admin(client, make_user)
    leak = await client.post(
        "/api/v1/integrations",
        json={
            "provider": "product_api",
            "name": "CRM",
            "config": {"base_url": "https://crm.example.com"},
            "secret_ref": "SECRET_KEY",
        },
        headers=h,
    )
    assert leak.status_code == 400
    assert leak.json()["error"]["code"] == "invalid_secret_ref"
    missing = await client.post(
        "/api/v1/integrations",
        json={"provider": "vercel", "name": "Site", "config": {"project_id": "abc"}},
        headers=h,
    )
    assert missing.json()["error"]["code"] == "secret_required"


async def test_ssrf_internal_addresses_rejected(client, make_user, monkeypatch):
    h = await _admin(client, make_user)
    monkeypatch.setattr(integration_http, "resolve_host", lambda host: ["10.0.0.5"])
    r = await client.post(
        "/api/v1/integrations",
        json={
            "provider": "http_monitor",
            "name": "Internal",
            "config": {"url": "https://intranet.example"},
        },
        headers=h,
    )
    assert r.status_code == 400
    assert "internal network" in r.json()["error"]["message"]
    plain = await client.post(
        "/api/v1/integrations",
        json={"provider": "http_monitor", "name": "Plain", "config": {"url": "http://example.com"}},
        headers=h,
    )
    assert plain.status_code == 400


async def test_product_api_sync_stores_only_numeric_aggregates(
    client, make_user, external, monkeypatch, db
):
    h = await _admin(client, make_user)
    monkeypatch.setenv("INTEGRATION_CRM_KEY", "crm-test-key")
    seen = {}

    def metrics(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "period": "2026-11-12",
                "metrics": {"active_customers": 42, "mrr": 125000.5, "name": "x", "flag": True},
            },
        )

    external(
        {
            ("GET", "https://crm.example.com/orbit/health"): lambda r: httpx.Response(
                200, json={"status": "ok", "version": "3.1"}
            ),
            ("GET", "https://crm.example.com/orbit/metrics"): metrics,
        }
    )
    created = await client.post(
        "/api/v1/integrations",
        json={
            "provider": "product_api",
            "name": "Eranova CRM",
            "config": {"base_url": "https://crm.example.com/"},
            "secret_ref": "INTEGRATION_CRM_KEY",
        },
        headers=h,
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    assert created.json()["webhook_url"].endswith(f"/api/v1/webhooks/product_api/{cid}")

    test = (await client.post(f"/api/v1/integrations/{cid}/test", headers=h)).json()
    assert test["ok"] is True and "ok" in test["message"]
    run = (await client.post(f"/api/v1/integrations/{cid}/sync", headers=h)).json()
    assert run["status"] == "success" and run["summary"] == {"metrics": 2}
    assert seen["auth"] == "Bearer crm-test-key"

    record = await db.scalar(
        select(IntegrationRecord).where(IntegrationRecord.kind == "product_metrics")
    )
    assert record.data["metrics"] == {"active_customers": 42, "mrr": 125000.5}
    detail = (await client.get(f"/api/v1/integrations/{cid}")).json()
    assert detail["last_success_at"] and detail["is_stale"] is False
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "integration.create"))
    assert "crm-test-key" not in json.dumps(audit.details)


async def test_failed_sync_is_visible_not_swallowed(client, make_user, external, monkeypatch):
    h = await _admin(client, make_user)
    monkeypatch.setenv("INTEGRATION_CRM_KEY", "wrong")
    external({("GET", "https://crm.example.com/orbit/metrics"): lambda r: httpx.Response(401)})
    cid = (
        await client.post(
            "/api/v1/integrations",
            json={
                "provider": "product_api",
                "name": "CRM",
                "config": {"base_url": "https://crm.example.com"},
                "secret_ref": "INTEGRATION_CRM_KEY",
            },
            headers=h,
        )
    ).json()["id"]
    run = (await client.post(f"/api/v1/integrations/{cid}/sync", headers=h)).json()
    assert run["status"] == "failed"
    assert "rejected the credentials" in run["error"]
    detail = (await client.get(f"/api/v1/integrations/{cid}")).json()
    assert detail["status"] == "error" and detail["last_error"]


async def test_missing_server_secret_reported(client, make_user, external, monkeypatch):
    h = await _admin(client, make_user)
    monkeypatch.delenv("INTEGRATION_NOT_SET", raising=False)
    cid = (
        await client.post(
            "/api/v1/integrations",
            json={
                "provider": "vercel",
                "name": "Site",
                "config": {"project_id": "prj_1"},
                "secret_ref": "INTEGRATION_NOT_SET",
            },
            headers=h,
        )
    ).json()["id"]
    result = (await client.post(f"/api/v1/integrations/{cid}/test", headers=h)).json()
    assert result["ok"] is False
    assert "INTEGRATION_NOT_SET" in result["message"]


async def test_github_sync_and_signed_webhook_adds_task_evidence(
    client, make_user, external, monkeypatch, db
):
    h = await _admin(client, make_user)
    monkeypatch.setenv("INTEGRATION_GH_HOOK", "hook-secret")
    external(
        {
            ("GET", "https://api.github.com/repos/eranova/shulepoa/pulls"): lambda r: (
                httpx.Response(
                    200,
                    json=[
                        {
                            "number": 12,
                            "title": "Fee module",
                            "html_url": "https://github.com/eranova/shulepoa/pull/12",
                            "user": {"login": "dev"},
                            "draft": False,
                        }
                    ],
                )
            ),
            ("GET", "https://api.github.com/repos/eranova/shulepoa"): lambda r: httpx.Response(
                200,
                json={
                    "full_name": "eranova/shulepoa",
                    "html_url": "https://github.com/eranova/shulepoa",
                    "open_issues_count": 3,
                    "default_branch": "main",
                },
            ),
        }
    )
    cid = (
        await client.post(
            "/api/v1/integrations",
            json={
                "provider": "github",
                "name": "ShulePoa repo",
                "config": {"owner": "eranova", "repo": "shulepoa"},
                "webhook_secret_ref": "INTEGRATION_GH_HOOK",
            },
            headers=h,
        )
    ).json()["id"]
    run = (await client.post(f"/api/v1/integrations/{cid}/sync", headers=h)).json()
    assert run["summary"] == {"open_pull_requests": 1}

    project = (
        await client.post("/api/v1/projects", json={"name": "ShulePoa v2"}, headers=h)
    ).json()
    task = (
        await client.post(
            "/api/v1/tasks", json={"project_id": project["id"], "title": "Fee module"}, headers=h
        )
    ).json()
    await client.post(
        f"/api/v1/tasks/{task['id']}/links",
        json={"kind": "github_pr", "url": "https://github.com/eranova/shulepoa/pull/12"},
        headers=h,
    )

    body = json.dumps(
        {
            "action": "closed",
            "pull_request": {
                "number": 12,
                "title": "Fee module",
                "html_url": "https://github.com/eranova/shulepoa/pull/12",
                "state": "closed",
                "merged": True,
            },
        }
    ).encode()
    signature = "sha256=" + hmac.new(b"hook-secret", body, hashlib.sha256).hexdigest()
    client.cookies.clear()
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "d-1",
        "X-Hub-Signature-256": signature,
        "Content-Type": "application/json",
    }

    forged = await client.post(
        f"/api/v1/webhooks/github/{cid}",
        content=body,
        headers=headers | {"X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert forged.status_code == 403
    ok = await client.post(f"/api/v1/webhooks/github/{cid}", content=body, headers=headers)
    assert ok.json() == {"status": "processed"}
    again = await client.post(f"/api/v1/webhooks/github/{cid}", content=body, headers=headers)
    assert again.json() == {"status": "duplicate"}

    evidence = await db.scalar(select(TaskEvent).where(TaskEvent.kind == "evidence"))
    assert "PR #12" in evidence.to_value
    await login(client, "root@eranova.co.ke")
    assert (await client.get(f"/api/v1/tasks/{task['id']}")).json()["status"] == "created"


async def test_product_webhook_replay_window(client, make_user, external, monkeypatch):
    h = await _admin(client, make_user)
    monkeypatch.setenv("INTEGRATION_CRM_KEY", "k")
    monkeypatch.setenv("INTEGRATION_CRM_HOOK", "hook")
    cid = (
        await client.post(
            "/api/v1/integrations",
            json={
                "provider": "product_api",
                "name": "CRM",
                "config": {"base_url": "https://crm.example.com"},
                "secret_ref": "INTEGRATION_CRM_KEY",
                "webhook_secret_ref": "INTEGRATION_CRM_HOOK",
            },
            headers=h,
        )
    ).json()["id"]
    body = b'{"type": "customer.created", "id": "evt-1"}'

    def signed(ts):
        sig = hmac.new(b"hook", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        return {
            "X-Orbit-Timestamp": str(ts),
            "X-Orbit-Signature": sig,
            "X-Orbit-Delivery": f"evt-{ts}",
        }

    stale = await client.post(
        f"/api/v1/webhooks/product_api/{cid}", content=body, headers=signed(int(time.time()) - 3600)
    )
    assert stale.status_code == 403
    fresh = await client.post(
        f"/api/v1/webhooks/product_api/{cid}", content=body, headers=signed(int(time.time()))
    )
    assert fresh.json()["status"] == "processed"


async def test_product_operations_and_monitoring_views(client, make_user, external, monkeypatch):
    h = await _admin(client, make_user)
    product = (
        await client.post(
            "/api/v1/products", json={"name": "ShulePoa", "slug": "shulepoa"}, headers=h
        )
    ).json()
    external({("GET", "https://shulepoa.example/health"): lambda r: httpx.Response(200, text="ok")})
    monkeypatch.setattr(
        "app.integrations.http_monitor._certificate_expiry",
        lambda host, port: "2027-01-01T00:00:00+00:00",
    )
    cid = (
        await client.post(
            "/api/v1/integrations",
            json={
                "provider": "http_monitor",
                "name": "ShulePoa uptime",
                "product_id": product["id"],
                "config": {"url": "https://shulepoa.example/health"},
            },
            headers=h,
        )
    ).json()["id"]
    await client.post(f"/api/v1/integrations/{cid}/sync", headers=h)

    ops = (await client.get(f"/api/v1/products/{product['id']}/operations")).json()
    assert ops["uptime"]["data"]["up"] is True
    assert ops["freshness"]["http_monitor"]["source"] == "ShulePoa uptime"
    monitoring = (await client.get("/api/v1/monitoring/overview")).json()
    assert monitoring["monitors"][0]["uptime_percent"] == 100.0
    assert monitoring["monitors"][0]["latest"]["data"]["certificate_expires_at"].startswith("2027")


async def test_worker_runs_due_syncs(client, make_user, external, monkeypatch, db):
    from app import worker

    h = await _admin(client, make_user)
    external({("GET", "https://shulepoa.example/health"): lambda r: httpx.Response(503)})
    monkeypatch.setattr(
        "app.integrations.http_monitor._certificate_expiry", lambda host, port: None
    )
    await client.post(
        "/api/v1/integrations",
        json={
            "provider": "http_monitor",
            "name": "Uptime",
            "config": {"url": "https://shulepoa.example/health"},
        },
        headers=h,
    )
    await worker.sync_due_integrations(db)
    run = await db.scalar(select(SyncRun))
    assert run.trigger == "scheduled" and run.status == "success"
    record = await db.scalar(
        select(IntegrationRecord).where(IntegrationRecord.kind == "uptime_check")
    )
    assert record.data["up"] is False and record.data["status"] == 503


async def test_integration_access_follows_product_scope(client, make_user, external):
    import uuid

    h = await _admin(client, make_user)
    a = (
        await client.post("/api/v1/products", json={"name": "Alpha", "slug": "alpha"}, headers=h)
    ).json()
    b = (
        await client.post("/api/v1/products", json={"name": "Bravo", "slug": "bravo"}, headers=h)
    ).json()
    for product, name in ((a, "Alpha up"), (b, "Bravo up")):
        await client.post(
            "/api/v1/integrations",
            json={
                "provider": "http_monitor",
                "name": name,
                "product_id": product["id"],
                "config": {"url": "https://x.example"},
            },
            headers=h,
        )
    await make_user(
        "pm@eranova.co.ke",
        role="product_manager",
        scope_type="product",
        scope_id=uuid.UUID(a["id"]),
    )
    await login(client, "pm@eranova.co.ke")
    names = [c["name"] for c in (await client.get("/api/v1/integrations")).json()]
    assert names == ["Alpha up"]
