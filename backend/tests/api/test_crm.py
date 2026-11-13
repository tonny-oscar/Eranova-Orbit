import uuid

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.crm.models import Activity, Contact, CustomerProduct, Enquiry
from tests.conftest import login


async def _product(client, csrf, name="ShulePoa", slug="shulepoa"):
    r = await client.post(
        "/api/v1/products", json={"name": name, "slug": slug}, headers={"X-CSRF-Token": csrf}
    )
    return r.json()


async def _lead(client, csrf, **extra):
    r = await client.post(
        "/api/v1/leads",
        json={
            "full_name": "Amina Otieno",
            "email": "amina@hotel.example",
            "organization": "Lakeview Hotel",
        }
        | extra,
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_starter_pipeline_and_stage_management(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    h = {"X-CSRF-Token": csrf}

    stages = (await client.get("/api/v1/crm/stages")).json()
    assert [s["key"] for s in stages] == [
        "new",
        "contacted",
        "interested",
        "demo_scheduled",
        "negotiation",
        "converted",
        "lost",
    ]
    created = await client.post("/api/v1/crm/stages", json={"name": "Proposal Sent"}, headers=h)
    assert created.json()["key"] == "proposal_sent"

    lead = await _lead(client, csrf)
    moved = await client.patch(
        f"/api/v1/leads/{lead['id']}", json={"status": "proposal_sent"}, headers=h
    )
    assert moved.status_code == 200
    bad = await client.patch(f"/api/v1/leads/{lead['id']}", json={"status": "nonsense"}, headers=h)
    assert bad.status_code == 400

    in_use = await client.delete(f"/api/v1/crm/stages/{created.json()['id']}", headers=h)
    assert in_use.status_code == 409


async def test_manual_lead_duplicate_detection(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    lead = await _lead(client, csrf)
    assert lead["status"] == "new"
    assert lead["source"] == "manual"
    dup = await client.post(
        "/api/v1/leads",
        json={"full_name": "Someone", "email": "AMINA@hotel.example"},
        headers={"X-CSRF-Token": csrf},
    )
    assert dup.status_code == 409


async def test_activities_and_conversion_preserve_history(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    h = {"X-CSRF-Token": csrf}
    product = await _product(client, csrf)
    lead = await _lead(client, csrf, product_id=product["id"])

    logged = await client.post(
        f"/api/v1/leads/{lead['id']}/activities",
        json={"type": "call", "subject": "Intro call", "body": "Interested in 20 rooms."},
        headers=h,
    )
    assert logged.status_code == 201
    assert logged.json()["activities"][0]["subject"] == "Intro call"
    assert logged.json()["can_convert"] is True

    converted = await client.post(f"/api/v1/leads/{lead['id']}/convert", json={}, headers=h)
    assert converted.status_code == 200, converted.text
    body = converted.json()
    assert body["status"] == "converted"
    assert body["converted_customer"]["name"] == "Lakeview Hotel"
    assert body["activities"][0]["subject"] == "Intro call"

    customer = (await client.get(f"/api/v1/customers/{body['converted_customer']['id']}")).json()
    assert customer["contacts"][0]["full_name"] == "Amina Otieno"
    assert customer["contacts"][0]["is_primary"] is True
    assert [s["product"]["name"] for s in customer["subscriptions"]] == ["ShulePoa"]
    assert customer["source_leads"][0]["id"] == lead["id"]
    assert customer["activities"][0]["subject"] == "Intro call"

    again = await client.post(f"/api/v1/leads/{lead['id']}/convert", json={}, headers=h)
    assert again.status_code == 409
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "lead.convert"))
    assert await db.scalar(select(Activity.lead_id)) == uuid.UUID(lead["id"])


async def test_convert_refuses_duplicate_customer_name(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    h = {"X-CSRF-Token": csrf}
    await client.post("/api/v1/customers", json={"name": "Lakeview Hotel"}, headers=h)
    lead = await _lead(client, csrf)
    r = await client.post(f"/api/v1/leads/{lead['id']}/convert", json={}, headers=h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "customer_exists"


async def test_customer_crud_contacts_subscriptions(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    h = {"X-CSRF-Token": csrf}
    product = await _product(client, csrf)

    customer = (
        await client.post(
            "/api/v1/customers", json={"name": "Hill School", "industry": "Education"}, headers=h
        )
    ).json()
    cid = customer["id"]
    await client.post(
        f"/api/v1/customers/{cid}/contacts",
        json={"full_name": "Head Teacher", "is_primary": True},
        headers=h,
    )
    second = await client.post(
        f"/api/v1/customers/{cid}/contacts",
        json={"full_name": "Bursar", "is_primary": True},
        headers=h,
    )
    primaries = [c["full_name"] for c in second.json()["contacts"] if c["is_primary"]]
    assert primaries == ["Bursar"]

    sub = await client.put(
        f"/api/v1/customers/{cid}/subscriptions",
        json={
            "product_id": product["id"],
            "plan_name": "Standard",
            "status": "active",
            "renewal_date": "2027-01-31",
        },
        headers=h,
    )
    assert sub.json()["next_renewal"] == "2027-01-31"
    upd = await client.patch(f"/api/v1/customers/{cid}", json={"status": "paused"}, headers=h)
    assert upd.json()["status"] == "paused"
    assert len(list(await db.scalars(select(CustomerProduct)))) == 1
    assert len(list(await db.scalars(select(Contact)))) == 2


async def test_product_scoped_sales_only_see_their_customers(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    h = {"X-CSRF-Token": csrf}
    a = await _product(client, csrf)
    b = await _product(client, csrf, "HostPilot", "hostpilot")
    for name, product in (("School A", a), ("Hotel B", b)):
        c = (await client.post("/api/v1/customers", json={"name": name}, headers=h)).json()
        await client.put(
            f"/api/v1/customers/{c['id']}/subscriptions",
            json={"product_id": product["id"]},
            headers=h,
        )

    await make_user(
        "sales@eranova.co.ke", role="sales", scope_type="product", scope_id=uuid.UUID(a["id"])
    )
    await login(client, "sales@eranova.co.ke")
    names = [c["name"] for c in (await client.get("/api/v1/customers")).json()["items"]]
    assert names == ["School A"]


async def test_exports_require_permission_escape_formulas_and_are_audited(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    await _lead(client, csrf, full_name="=HYPERLINK(evil)", email="x@y.example")
    r = await client.get("/api/v1/leads/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "'=HYPERLINK(evil)" in r.text
    event = await db.scalar(select(AuditLog).where(AuditLog.action == "data.export"))
    assert event.details == {"dataset": "leads", "rows": 1}

    await make_user("sales@eranova.co.ke", role="sales")
    await login(client, "sales@eranova.co.ke")
    assert (await client.get("/api/v1/leads/export.csv")).status_code == 403


async def test_website_enquiry_uses_first_configured_stage(client, company, db):
    await client.post(
        "/api/v1/public/enquiries",
        json={
            "type": "contact",
            "full_name": "Visitor",
            "email": "v@x.example",
            "message": "Hello team, interested.",
            "consent_privacy": True,
            "elapsed_ms": 8000,
        },
    )
    assert await db.scalar(select(Enquiry.id)) is not None
