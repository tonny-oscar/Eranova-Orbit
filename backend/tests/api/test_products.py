import uuid

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.authorization.models import Role, UserRole
from app.modules.products.models import Product
from tests.conftest import login

PRODUCTS = "/api/v1/products"


async def _create(client, csrf, **overrides):
    payload = {"name": "ShulePoa", "slug": "shulepoa", "category": "Education"} | overrides
    return await client.post(PRODUCTS, json=payload, headers={"X-CSRF-Token": csrf})


async def test_super_admin_registers_product_with_history_and_audit(client, make_user, db):
    admin = await make_user("root@eranova.co.ke", role="super_admin", full_name="Root")
    csrf = await login(client, "root@eranova.co.ke")

    response = await _create(
        client,
        csrf,
        owner_user_id=str(admin.id),
        website_url="https://shulepoa.example",
        pricing=[
            {"name": "Starter", "amount": "1500.00", "currency": "KES", "interval": "monthly"}
        ],
        launch_date="2026-01-15",
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["lifecycle_status"] == "draft"
    assert body["details_confirmed"] is False
    assert body["owner"]["email"] == "root@eranova.co.ke"
    assert body["pricing"][0]["amount"] == "1500.00"
    assert body["can_update"] and body["can_manage"]

    history = await client.get(f"{PRODUCTS}/{body['id']}/status-history")
    assert [h["to_status"] for h in history.json()] == ["draft"]
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "product.create"))


async def test_duplicate_slug_and_invalid_input_are_rejected(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    assert (await _create(client, csrf)).status_code == 201

    duplicate = await _create(client, csrf, name="Other")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "product_slug_taken"

    bad_slug = await _create(client, csrf, name="Bad", slug="Bad Slug!")
    assert bad_slug.status_code == 422

    bad_url = await _create(
        client, csrf, name="Bad2", slug="bad2", website_url="javascript:alert(1)"
    )
    assert bad_url.status_code == 422


async def test_product_scoped_user_sees_and_edits_only_their_product(
    client, make_user, db, company
):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    mine = (await _create(client, csrf)).json()
    other = (await _create(client, csrf, name="HostPilot", slug="hostpilot")).json()

    pm = await make_user(
        "pm@eranova.co.ke",
        role="product_manager",
        scope_type="product",
        scope_id=uuid.UUID(mine["id"]),
    )
    assert pm.id
    pm_csrf = await login(client, "pm@eranova.co.ke")

    listing = await client.get(PRODUCTS)
    assert [p["slug"] for p in listing.json()["items"]] == ["shulepoa"]
    assert (await client.get(f"{PRODUCTS}/{other['id']}")).status_code == 404

    edit = await client.patch(
        f"{PRODUCTS}/{mine['id']}",
        json={"tagline": "School management"},
        headers={"X-CSRF-Token": pm_csrf},
    )
    assert edit.status_code == 200
    assert edit.json()["tagline"] == "School management"
    assert edit.json()["can_manage"] is False

    blocked = await client.patch(
        f"{PRODUCTS}/{other['id']}", json={"tagline": "x"}, headers={"X-CSRF-Token": pm_csrf}
    )
    assert blocked.status_code == 404

    cannot_create = await _create(client, pm_csrf, name="New", slug="new")
    assert cannot_create.status_code == 403


async def test_status_change_records_history(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    product = (await _create(client, csrf)).json()

    changed = await client.post(
        f"{PRODUCTS}/{product['id']}/status",
        json={"status": "live", "reason": "Launched"},
        headers={"X-CSRF-Token": csrf},
    )
    assert changed.status_code == 200
    assert changed.json()["lifecycle_status"] == "live"

    same = await client.post(
        f"{PRODUCTS}/{product['id']}/status",
        json={"status": "live"},
        headers={"X-CSRF-Token": csrf},
    )
    assert same.status_code == 400

    history = (await client.get(f"{PRODUCTS}/{product['id']}/status-history")).json()
    assert [(h["from_status"], h["to_status"]) for h in history] == [
        ("draft", "live"),
        (None, "draft"),
    ]
    event = await db.scalar(select(AuditLog).where(AuditLog.action == "product.status.change"))
    assert event.details["to"] == "live"


async def test_update_audits_changed_fields(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    product = (await _create(client, csrf)).json()

    response = await client.patch(
        f"{PRODUCTS}/{product['id']}",
        json={"details_confirmed": True, "website_url": None},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    event = await db.scalar(select(AuditLog).where(AuditLog.action == "product.update"))
    assert event.details["changes"]["details_confirmed"] == {"from": False, "to": True}

    cannot_clear_name = await client.patch(
        f"{PRODUCTS}/{product['id']}", json={"name": None}, headers={"X-CSRF-Token": csrf}
    )
    assert cannot_clear_name.status_code == 400


async def test_team_members_require_manage(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    dev = await make_user("dev@eranova.co.ke", role="developer", full_name="Dev")
    csrf = await login(client, "root@eranova.co.ke")
    product = (await _create(client, csrf)).json()

    added = await client.post(
        f"{PRODUCTS}/{product['id']}/members",
        json={"user_id": str(dev.id), "team_role": "Backend developer"},
        headers={"X-CSRF-Token": csrf},
    )
    assert added.status_code == 201
    duplicate = await client.post(
        f"{PRODUCTS}/{product['id']}/members",
        json={"user_id": str(dev.id)},
        headers={"X-CSRF-Token": csrf},
    )
    assert duplicate.status_code == 409

    dev_csrf = await login(client, "dev@eranova.co.ke")
    members = await client.get(f"{PRODUCTS}/{product['id']}/members")
    assert [m["user"]["email"] for m in members.json()] == ["dev@eranova.co.ke"]
    denied = await client.delete(
        f"{PRODUCTS}/{product['id']}/members/{added.json()['id']}",
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert denied.status_code == 403


async def test_product_scope_role_assignment_validates_target(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    target = await make_user("pm@eranova.co.ke")
    csrf = await login(client, "root@eranova.co.ke")
    product = (await _create(client, csrf)).json()
    role_id = await db.scalar(select(Role.id).where(Role.slug == "product_manager"))

    missing = await client.post(
        f"/api/v1/users/{target.id}/roles",
        json={"role_id": str(role_id), "scope_type": "product", "scope_id": str(uuid.uuid4())},
        headers={"X-CSRF-Token": csrf},
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "invalid_scope"

    ok = await client.post(
        f"/api/v1/users/{target.id}/roles",
        json={"role_id": str(role_id), "scope_type": "product", "scope_id": product["id"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert ok.status_code == 201
    assert await db.scalar(
        select(UserRole.scope_id).where(UserRole.user_id == target.id)
    ) == uuid.UUID(product["id"])


async def test_register_initial_products_is_idempotent_and_unconfirmed(db, company):
    from app.cli import register_initial_products

    first = await register_initial_products(db)
    second = await register_initial_products(db)
    assert first == ["shulepoa", "hostpilot", "otpguard", "sitepoa", "menupoa"]
    assert second == []
    products = list(await db.scalars(select(Product)))
    assert all(p.lifecycle_status == "draft" and not p.details_confirmed for p in products)
    assert all(p.description == "" for p in products)


async def test_list_filters_by_search_and_status(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    await _create(client, csrf)
    await _create(client, csrf, name="OTPGuard", slug="otpguard", category="Security")

    by_search = await client.get(PRODUCTS, params={"q": "secur"})
    assert [p["slug"] for p in by_search.json()["items"]] == ["otpguard"]
    by_status = await client.get(PRODUCTS, params={"status": "live"})
    assert by_status.json()["total"] == 0
    assert await db.scalar(select(Product.id).where(Product.slug == "otpguard"))
