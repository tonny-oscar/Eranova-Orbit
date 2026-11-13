import uuid

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.crm.models import Enquiry, Lead
from tests.conftest import login

PRODUCTS = "/api/v1/products"


async def _publishable_product(client, csrf, **overrides):
    payload = {
        "name": "ShulePoa",
        "slug": "shulepoa",
        "category": "Education",
        "description": "School management for Kenyan schools.",
        "details_confirmed": True,
        "lifecycle_status": "live",
        "features": [{"title": "Fee tracking", "description": "Record payments."}],
    } | overrides
    response = await client.post(PRODUCTS, json=payload, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201, response.text
    return response.json()


def _enquiry(**overrides):
    return {
        "type": "contact",
        "full_name": "Wanjiku Mwangi",
        "email": "Wanjiku@School.example",
        "organization": "Hill School",
        "message": "We would like to learn more.",
        "consent_privacy": True,
        "elapsed_ms": 8_000,
        "attribution": {"utm_source": "google", "landing_page": "/products/shulepoa"},
    } | overrides


# --- Publishing ---------------------------------------------------------------


async def test_unpublished_products_are_not_public(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    await _publishable_product(client, csrf)

    assert (await client.get("/api/v1/public/products")).json() == []
    assert (await client.get("/api/v1/public/products/shulepoa")).status_code == 404


async def test_publish_requires_confirmed_public_status_and_description(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    headers = {"X-CSRF-Token": csrf}
    draft = await _publishable_product(
        client,
        csrf,
        name="Draft",
        slug="draft",
        details_confirmed=False,
        lifecycle_status="draft",
        description="",
    )
    response = await client.post(f"{PRODUCTS}/{draft['id']}/publish", headers=headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "not_publishable"
    assert len(response.json()["error"]["details"]) == 3


async def test_published_product_is_public_without_internal_fields(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    product = await _publishable_product(
        client, csrf, repository_url="https://github.com/eranova/secret-repo"
    )
    published = await client.post(
        f"{PRODUCTS}/{product['id']}/publish", headers={"X-CSRF-Token": csrf}
    )
    assert published.status_code == 200
    assert published.json()["is_public"] is True

    client.cookies.clear()
    listing = await client.get("/api/v1/public/products")
    assert [p["slug"] for p in listing.json()] == ["shulepoa"]
    detail = (await client.get("/api/v1/public/products/shulepoa")).json()
    assert detail["features"][0]["title"] == "Fee tracking"
    for internal in ("id", "repository_url", "owner", "deployment_ref", "analytics_property_id"):
        assert internal not in detail
    assert "public" in (await client.get("/api/v1/public/products")).headers["cache-control"]


async def test_unconfirming_hides_a_published_product(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    product = await _publishable_product(client, csrf)
    await client.post(f"{PRODUCTS}/{product['id']}/publish", headers={"X-CSRF-Token": csrf})
    await client.patch(
        f"{PRODUCTS}/{product['id']}",
        json={"details_confirmed": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert (await client.get("/api/v1/public/products")).json() == []


async def test_product_manager_cannot_publish(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    product = await _publishable_product(client, csrf)
    await make_user(
        "pm@eranova.co.ke",
        role="product_manager",
        scope_type="product",
        scope_id=uuid.UUID(product["id"]),
    )
    pm_csrf = await login(client, "pm@eranova.co.ke")
    response = await client.post(
        f"{PRODUCTS}/{product['id']}/publish", headers={"X-CSRF-Token": pm_csrf}
    )
    assert response.status_code == 403


# --- Website content -------------------------------------------------------------


async def test_content_draft_publish_cycle(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    headers = {"X-CSRF-Token": csrf}

    assert (await client.get("/api/v1/public/pages/about")).status_code == 404
    pages = (await client.get("/api/v1/content/pages")).json()
    assert {p["slug"] for p in pages} >= {"home", "about", "privacy"}

    saved = await client.put(
        "/api/v1/content/pages/about",
        json={
            "title": "About Eranova",
            "summary": "Who we are.",
            "sections": [
                {"heading": "Mission", "body": "Build useful software."},
                {"heading": "", "body": ""},
            ],
        },
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json()["published"] is None
    assert len(saved.json()["draft"]["sections"]) == 1
    assert (await client.get("/api/v1/public/pages/about")).status_code == 404

    published = await client.post("/api/v1/content/pages/about/publish", headers=headers)
    assert published.json()["has_unpublished_changes"] is False
    public = (await client.get("/api/v1/public/pages/about")).json()
    assert public["title"] == "About Eranova"

    await client.put(
        "/api/v1/content/pages/about",
        json={"title": "About us (new draft)", "sections": []},
        headers=headers,
    )
    assert (await client.get("/api/v1/public/pages/about")).json()["title"] == "About Eranova"

    site = (await client.get("/api/v1/public/site")).json()
    assert site["published_pages"] == ["about"]
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "content.publish"))


async def test_content_roles_and_unknown_pages(client, make_user):
    await make_user("mkt@eranova.co.ke", role="marketing")
    csrf = await login(client, "mkt@eranova.co.ke")
    headers = {"X-CSRF-Token": csrf}

    draft = await client.put(
        "/api/v1/content/pages/home", json={"title": "Welcome", "summary": "Hi"}, headers=headers
    )
    assert draft.status_code == 200
    assert draft.json()["can_publish"] is False
    assert (
        await client.post("/api/v1/content/pages/home/publish", headers=headers)
    ).status_code == 403
    assert (await client.get("/api/v1/content/pages/secret")).status_code == 404
    assert (await client.get("/api/v1/public/pages/secret")).status_code == 404


# --- Enquiries and leads -----------------------------------------------------------


async def test_enquiry_creates_lead_with_consent_and_attribution(client, make_user, db, company):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    product = await _publishable_product(client, csrf)
    await client.post(f"{PRODUCTS}/{product['id']}/publish", headers={"X-CSRF-Token": csrf})
    client.cookies.clear()

    response = await client.post(
        "/api/v1/public/enquiries",
        json=_enquiry(type="demo", product_slug="shulepoa", preferred_date="2030-01-15"),
    )
    assert response.status_code == 202

    lead = await db.scalar(select(Lead))
    assert lead.email == "wanjiku@school.example"
    assert lead.source == "website_demo"
    assert str(lead.product_id) == product["id"]
    enquiry = await db.scalar(select(Enquiry))
    assert enquiry.consent_privacy is True
    assert enquiry.privacy_notice_version
    assert enquiry.utm_source == "google"
    assert enquiry.ip_hash and "127.0.0.1" not in enquiry.ip_hash


async def test_repeat_enquiry_updates_the_same_lead(client, company, db):
    await client.post("/api/v1/public/enquiries", json=_enquiry())
    await client.post(
        "/api/v1/public/enquiries",
        json=_enquiry(
            email="wanjiku@school.example", phone="+254 700 000 000", consent_marketing=True
        ),
    )
    leads = list(await db.scalars(select(Lead)))
    assert len(leads) == 1
    assert leads[0].phone == "+254 700 000 000"
    assert leads[0].marketing_consent is True
    assert len(list(await db.scalars(select(Enquiry)))) == 2


async def test_enquiry_requires_privacy_consent(client, company):
    response = await client.post("/api/v1/public/enquiries", json=_enquiry(consent_privacy=False))
    assert response.status_code == 422


async def test_spam_submissions_look_accepted_but_store_nothing(client, company, db):
    honeypot = await client.post("/api/v1/public/enquiries", json=_enquiry(website="http://spam"))
    too_fast = await client.post("/api/v1/public/enquiries", json=_enquiry(elapsed_ms=200))
    assert honeypot.status_code == too_fast.status_code == 202
    assert await db.scalar(select(Lead.id)) is None


async def test_enquiries_are_rate_limited(client, company):
    statuses = [
        (
            await client.post("/api/v1/public/enquiries", json=_enquiry(email=f"p{i}@x.example"))
        ).status_code
        for i in range(6)
    ]
    assert statuses[:5] == [202] * 5
    assert statuses[5] == 429


async def test_unpublished_product_slug_is_ignored(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    await _publishable_product(client, csrf)
    client.cookies.clear()
    await client.post("/api/v1/public/enquiries", json=_enquiry(product_slug="shulepoa"))
    assert (await db.scalar(select(Lead))).product_id is None


async def test_sales_scoped_to_product_see_only_its_leads(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    a = await _publishable_product(client, csrf)
    b = await _publishable_product(client, csrf, name="HostPilot", slug="hostpilot")
    for p in (a, b):
        await client.post(f"{PRODUCTS}/{p['id']}/publish", headers={"X-CSRF-Token": csrf})
    client.cookies.clear()
    await client.post("/api/v1/public/enquiries", json=_enquiry(product_slug="shulepoa"))
    await client.post(
        "/api/v1/public/enquiries",
        json=_enquiry(email="ops@hotel.example", product_slug="hostpilot"),
    )

    await make_user(
        "sales@eranova.co.ke", role="sales", scope_type="product", scope_id=uuid.UUID(a["id"])
    )
    sales_csrf = await login(client, "sales@eranova.co.ke")
    leads = (await client.get("/api/v1/leads")).json()
    assert [lead["email"] for lead in leads["items"]] == ["wanjiku@school.example"]
    lead_id = leads["items"][0]["id"]

    detail = (await client.get(f"/api/v1/leads/{lead_id}")).json()
    assert detail["enquiries"][0]["utm_source"] == "google"
    assert detail["can_update"] is True

    updated = await client.patch(
        f"/api/v1/leads/{lead_id}",
        json={"status": "contacted", "notes": "Called, follow up Friday."},
        headers={"X-CSRF-Token": sales_csrf},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "contacted"

    other = await db.scalar(select(Lead.id).where(Lead.email == "ops@hotel.example"))
    assert (await client.get(f"/api/v1/leads/{other}")).status_code == 404
    event = await db.scalar(select(AuditLog).where(AuditLog.action == "lead.update"))
    assert event.details["changes"]["status"] == {"from": "new", "to": "contacted"}
    assert "Called" not in str(event.details)


async def test_public_endpoints_need_no_session(client, company):
    assert (await client.get("/api/v1/public/site")).status_code == 200
    assert (await client.get("/api/v1/leads")).status_code == 401
