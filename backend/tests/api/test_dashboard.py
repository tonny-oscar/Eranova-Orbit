import uuid

from tests.conftest import login


async def _product(client, csrf, name, slug, **extra):
    response = await client.post(
        "/api/v1/products",
        json={"name": name, "slug": slug} | extra,
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201
    return response.json()


async def test_summary_for_super_admin_has_live_counts(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    await make_user("dev@eranova.co.ke", role="developer")
    csrf = await login(client, "root@eranova.co.ke")
    await _product(client, csrf, "ShulePoa", "shulepoa")
    await _product(
        client, csrf, "HostPilot", "hostpilot", lifecycle_status="live", details_confirmed=True
    )

    body = (await client.get("/api/v1/dashboard/summary")).json()
    assert body["generated_at"]
    assert body["source"].startswith("Orbit database")
    assert body["products"] == {
        "total": 2,
        "by_status": {"draft": 1, "live": 1},
        "unconfirmed": 1,
    }
    assert body["accounts"]["active"] == 2
    assert body["people"]["active"] == 2
    assert any(e["action"] == "product.create" for e in body["recent_activity"])


async def test_summary_omits_sections_without_permission(client, make_user):
    await make_user("someone@eranova.co.ke")
    await login(client, "someone@eranova.co.ke")
    body = (await client.get("/api/v1/dashboard/summary")).json()
    assert body["products"] is None
    assert body["people"] is None
    assert body["accounts"] is None
    assert body["recent_activity"] is None


async def test_summary_respects_product_scope(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    mine = await _product(client, csrf, "ShulePoa", "shulepoa")
    await _product(client, csrf, "HostPilot", "hostpilot")
    await make_user(
        "pm@eranova.co.ke",
        role="product_manager",
        scope_type="product",
        scope_id=uuid.UUID(mine["id"]),
    )
    await login(client, "pm@eranova.co.ke")

    body = (await client.get("/api/v1/dashboard/summary")).json()
    assert body["products"]["total"] == 1
    assert body["accounts"] is None


async def test_search_is_scoped_and_grouped(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin", full_name="Root Admin")
    await make_user("shiko@eranova.co.ke", full_name="Shiko Wanjiru")
    csrf = await login(client, "root@eranova.co.ke")
    mine = await _product(client, csrf, "ShulePoa", "shulepoa", category="Education")
    await _product(client, csrf, "OTPGuard", "otpguard")

    results = (await client.get("/api/v1/search", params={"q": "sh"})).json()["results"]
    assert {(r["type"], r["title"]) for r in results} == {
        ("product", "ShulePoa"),
        ("person", "Shiko Wanjiru"),
    }
    assert any(r["url"] == f"/app/products/{mine['id']}" for r in results)

    assert (await client.get("/api/v1/search", params={"q": "s"})).json()["results"] == []

    await make_user(
        "pm@eranova.co.ke",
        role="product_manager",
        scope_type="product",
        scope_id=uuid.UUID(mine["id"]),
    )
    await login(client, "pm@eranova.co.ke")
    scoped = (await client.get("/api/v1/search", params={"q": "otp"})).json()["results"]
    assert scoped == []


async def test_search_escapes_wildcards(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    await _product(client, csrf, "ShulePoa", "shulepoa")
    results = (await client.get("/api/v1/search", params={"q": "%%"})).json()["results"]
    assert results == []


async def test_dashboard_and_search_require_authentication(client):
    assert (await client.get("/api/v1/dashboard/summary")).status_code == 401
    assert (await client.get("/api/v1/search", params={"q": "ab"})).status_code == 401
