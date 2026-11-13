import uuid
from datetime import UTC, datetime, timedelta

from tests.conftest import login


async def _setup(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    await make_user("mkt@eranova.co.ke", role="marketing")
    admin = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    product = (
        await client.post(
            "/api/v1/products", json={"name": "ShulePoa", "slug": "shulepoa"}, headers=admin
        )
    ).json()
    return product


async def test_content_needs_independent_approval_and_confirmed_publication(client, make_user):
    product = await _setup(client, make_user)
    h = {"X-CSRF-Token": await login(client, "mkt@eranova.co.ke")}
    campaign = await client.post(
        "/api/v1/marketing/campaigns",
        json={
            "name": "Back to school",
            "product_id": product["id"],
            "channels": ["facebook", "email", "facebook"],
            "start_date": "2026-12-01",
            "end_date": "2026-12-31",
            "budget_amount": "50000",
            "budget_currency": "KES",
        },
        headers=h,
    )
    assert campaign.status_code == 201, campaign.text
    assert campaign.json()["channels"] == ["email", "facebook"]
    content = (
        await client.post(
            "/api/v1/marketing/content",
            json={
                "title": "Launch post",
                "kind": "social_caption",
                "channel": "facebook",
                "body": "Draft",
                "campaign_id": campaign.json()["id"],
            },
            headers=h,
        )
    ).json()
    assert content["product"]["id"] == product["id"]
    assert content["allowed_actions"] == ["submit"]

    cid = content["id"]
    submitted = (
        await client.post(
            f"/api/v1/marketing/content/{cid}/actions", json={"action": "submit"}, headers=h
        )
    ).json()
    assert submitted["status"] == "in_review"
    assert "approve" not in submitted["allowed_actions"]  # marketing role cannot approve

    admin = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    approved = (
        await client.post(
            f"/api/v1/marketing/content/{cid}/actions", json={"action": "approve"}, headers=admin
        )
    ).json()
    assert approved["status"] == "approved" and approved["approved_by"]

    h = {"X-CSRF-Token": await login(client, "mkt@eranova.co.ke")}
    locked = await client.patch(
        f"/api/v1/marketing/content/{cid}", json={"body": "sneaky edit"}, headers=h
    )
    assert locked.json()["error"]["code"] == "content_locked"

    past = await client.post(
        f"/api/v1/marketing/content/{cid}/actions",
        json={
            "action": "schedule",
            "scheduled_for": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        },
        headers=h,
    )
    assert past.json()["error"]["code"] == "invalid_schedule"
    when = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    scheduled = (
        await client.post(
            f"/api/v1/marketing/content/{cid}/actions",
            json={"action": "schedule", "scheduled_for": when},
            headers=h,
        )
    ).json()
    assert scheduled["status"] == "scheduled"

    no_link = await client.post(
        f"/api/v1/marketing/content/{cid}/actions", json={"action": "record_published"}, headers=h
    )
    assert no_link.json()["error"]["code"] == "published_url_required"
    published = (
        await client.post(
            f"/api/v1/marketing/content/{cid}/actions",
            json={
                "action": "record_published",
                "published_url": "https://facebook.com/eranova/posts/1",
            },
            headers=h,
        )
    ).json()
    assert published["status"] == "published"
    assert published["publish_method"] == "manual"
    assert published["published_by"]["id"]

    start = datetime.now(UTC) - timedelta(days=1)
    calendar = (
        await client.get(
            "/api/v1/marketing/calendar",
            params={"start": start.isoformat(), "end": (start + timedelta(days=30)).isoformat()},
        )
    ).json()
    assert [c["id"] for c in calendar["content"]] == [cid]
    assert calendar["campaigns"][0]["content_counts"] == {"published": 1}

    deleted = await client.delete(
        f"/api/v1/marketing/campaigns/{campaign.json()['id']}", headers=admin
    )
    assert deleted.status_code in (400, 403)


async def test_authors_cannot_approve_their_own_content(client, make_user):
    await _setup(client, make_user)
    admin = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    cid = (
        await client.post(
            "/api/v1/marketing/content", json={"title": "Email", "kind": "email"}, headers=admin
        )
    ).json()["id"]
    await client.post(
        f"/api/v1/marketing/content/{cid}/actions", json={"action": "submit"}, headers=admin
    )
    r = await client.post(
        f"/api/v1/marketing/content/{cid}/actions", json={"action": "approve"}, headers=admin
    )
    assert r.status_code == 403
    changes = await client.post(
        f"/api/v1/marketing/content/{cid}/actions",
        json={"action": "request_changes"},
        headers=admin,
    )
    assert changes.status_code in (400, 403)


async def test_campaigns_follow_product_scope(client, make_user):
    product = await _setup(client, make_user)
    admin = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    other = (
        await client.post(
            "/api/v1/products", json={"name": "HostPilot", "slug": "hostpilot"}, headers=admin
        )
    ).json()
    for p, name in ((product, "Schools"), (other, "Hosting")):
        await client.post(
            "/api/v1/marketing/campaigns", json={"name": name, "product_id": p["id"]}, headers=admin
        )
    await make_user(
        "pm@eranova.co.ke",
        role="product_manager",
        scope_type="product",
        scope_id=uuid.UUID(product["id"]),
    )
    h = {"X-CSRF-Token": await login(client, "pm@eranova.co.ke")}
    names = [c["name"] for c in (await client.get("/api/v1/marketing/campaigns")).json()["items"]]
    assert names == ["Schools"]
    denied = await client.post(
        "/api/v1/marketing/campaigns", json={"name": "Sneaky", "product_id": other["id"]}, headers=h
    )
    assert denied.status_code == 403


async def test_metrics_record_their_source(client, make_user):
    await _setup(client, make_user)
    admin = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    cid = (
        await client.post("/api/v1/marketing/campaigns", json={"name": "Launch"}, headers=admin)
    ).json()["id"]
    detail = (
        await client.post(
            f"/api/v1/marketing/campaigns/{cid}/metrics",
            json={
                "metric": "Leads generated",
                "value": "42",
                "source": "Facebook Ads Manager export",
            },
            headers=admin,
        )
    ).json()
    assert detail["metrics"][0]["source"] == "Facebook Ads Manager export"
    assert detail["metrics"][0]["recorded_by"]["id"]
