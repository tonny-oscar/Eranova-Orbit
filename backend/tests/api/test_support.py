import uuid

from tests.conftest import login


async def _admin(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    return {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}


async def test_ticket_lifecycle_and_history(client, make_user):
    h = await _admin(client, make_user)
    t = (
        await client.post(
            "/api/v1/support/tickets",
            json={
                "subject": "Cannot log in",
                "description": "Error 500",
                "requester_email": "head@school.example",
                "category": "bug",
                "priority": "high",
            },
            headers=h,
        )
    ).json()
    assert t["status"] == "new" and t["number"] >= 1001 and t["reference"] == f"T-{t['number']}"

    note = (
        await client.post(
            f"/api/v1/support/tickets/{t['id']}/messages",
            json={"body": "Checking logs", "internal": True},
            headers=h,
        )
    ).json()
    assert note["first_response_at"] is None and note["status"] == "new"
    reply = (
        await client.post(
            f"/api/v1/support/tickets/{t['id']}/messages", json={"body": "We are on it"}, headers=h
        )
    ).json()
    assert reply["first_response_at"] and reply["status"] == "open"

    bad = await client.post(
        f"/api/v1/support/tickets/{t['id']}/transition", json={"status": "assigned"}, headers=h
    )
    assert bad.json()["error"]["code"] == "assignee_required"
    no_resolution = await client.post(
        f"/api/v1/support/tickets/{t['id']}/transition", json={"status": "resolved"}, headers=h
    )
    assert no_resolution.json()["error"]["code"] == "resolution_required"
    resolved = (
        await client.post(
            f"/api/v1/support/tickets/{t['id']}/transition",
            json={"status": "resolved", "resolution": "Reset session store"},
            headers=h,
        )
    ).json()
    assert resolved["status"] == "resolved" and resolved["resolved_at"]

    customer = (
        await client.post(
            f"/api/v1/support/tickets/{t['id']}/messages",
            json={"body": "Still broken", "from_customer": True},
            headers=h,
        )
    ).json()
    assert customer["status"] == "open" and customer["resolved_at"] is None

    closed_jump = await client.post(
        f"/api/v1/support/tickets/{t['id']}/transition",
        json={"status": "waiting_customer"},
        headers=h,
    )
    assert closed_jump.status_code == 200
    invalid = await client.post(
        f"/api/v1/support/tickets/{t['id']}/transition", json={"status": "new"}, headers=h
    )
    assert invalid.json()["error"]["code"] == "invalid_transition"

    detail = (await client.get(f"/api/v1/support/tickets/{t['id']}")).json()
    kinds = [(e["kind"], e["to_value"]) for e in detail["events"]]
    assert ("created", "new") in kinds and ("status", "resolved") in kinds
    assert len(detail["messages"]) == 3

    found = (await client.get("/api/v1/support/tickets", params={"q": t["reference"]})).json()
    assert found["total"] == 1


async def test_assignment_notifies_and_scopes_by_product(client, make_user):
    h = await _admin(client, make_user)
    a = (
        await client.post("/api/v1/products", json={"name": "Alpha", "slug": "alpha"}, headers=h)
    ).json()
    b = (
        await client.post("/api/v1/products", json={"name": "Bravo", "slug": "bravo"}, headers=h)
    ).json()
    agent = await make_user(
        "agent@eranova.co.ke", role="support", scope_type="product", scope_id=uuid.UUID(a["id"])
    )
    mine = (
        await client.post(
            "/api/v1/support/tickets",
            json={
                "subject": "Alpha issue",
                "product_id": a["id"],
                "assignee_user_id": str(agent.id),
            },
            headers=h,
        )
    ).json()
    assert mine["status"] == "assigned"
    await client.post(
        "/api/v1/support/tickets", json={"subject": "Bravo issue", "product_id": b["id"]}, headers=h
    )

    await login(client, "agent@eranova.co.ke")
    subjects = [t["subject"] for t in (await client.get("/api/v1/support/tickets")).json()["items"]]
    assert subjects == ["Alpha issue"]
    bell = (await client.get("/api/v1/notifications")).json()
    assert any("assigned to you" in n["title"] for n in bell["items"])
    export = await client.get("/api/v1/support/tickets/export.csv")
    assert export.status_code == 403


async def test_metrics_are_computed_from_tickets(client, make_user):
    h = await _admin(client, make_user)
    empty = (await client.get("/api/v1/support/metrics")).json()
    assert empty["created"] == 0 and empty["median_first_response_hours"] is None
    t = (
        await client.post(
            "/api/v1/support/tickets",
            json={"subject": "Billing question", "category": "billing"},
            headers=h,
        )
    ).json()
    await client.post(
        f"/api/v1/support/tickets/{t['id']}/messages", json={"body": "Answered"}, headers=h
    )
    m = (await client.get("/api/v1/support/metrics")).json()
    assert m["created"] == 1 and m["open"] == 1
    assert m["by_category"] == {"billing": 1}
    assert m["median_first_response_hours"] is not None
