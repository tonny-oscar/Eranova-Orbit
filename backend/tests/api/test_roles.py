import uuid

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.authorization.models import Permission, Role, RolePermission, UserRole
from tests.conftest import login


async def _role_id(db, slug: str) -> uuid.UUID:
    return await db.scalar(select(Role.id).where(Role.slug == slug))


async def test_bootstrap_creates_starter_roles(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    await login(client, "root@eranova.co.ke")
    response = await client.get("/api/v1/roles")
    assert response.status_code == 200
    slugs = {r["slug"] for r in response.json()}
    assert {"super_admin", "executive", "developer", "auditor"} <= slugs
    super_admin = next(r for r in response.json() if r["slug"] == "super_admin")
    assert super_admin["is_locked"] is True


async def test_role_endpoints_require_permission(client, make_user):
    await make_user("dev@eranova.co.ke", role="developer")
    await login(client, "dev@eranova.co.ke")
    assert (await client.get("/api/v1/roles")).status_code == 403
    assert (await client.get("/api/v1/authz/permissions")).status_code == 403


async def test_super_admin_assigns_and_revokes_role(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    target = await make_user("sam@eranova.co.ke")
    csrf = await login(client, "root@eranova.co.ke")
    headers = {"X-CSRF-Token": csrf}

    created = await client.post(
        f"/api/v1/users/{target.id}/roles",
        json={"role_id": str(await _role_id(db, "sales")), "scope_type": "company"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    duplicate = await client.post(
        f"/api/v1/users/{target.id}/roles",
        json={"role_id": str(await _role_id(db, "sales"))},
        headers=headers,
    )
    assert duplicate.status_code == 409

    detail = await client.get(f"/api/v1/users/{target.id}")
    assert [r["role_slug"] for r in detail.json()["roles"]] == ["sales"]

    revoked = await client.delete(
        f"/api/v1/users/{target.id}/roles/{assignment_id}", headers=headers
    )
    assert revoked.status_code == 204

    actions = list(
        await db.scalars(
            select(AuditLog.action)
            .where(AuditLog.resource_id == str(target.id))
            .order_by(AuditLog.created_at)
        )
    )
    assert actions == ["role.assignment.create", "role.assignment.delete"]


async def test_cannot_change_own_roles(client, make_user, db):
    admin = await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    response = await client.post(
        f"/api/v1/users/{admin.id}/roles",
        json={"role_id": str(await _role_id(db, "auditor"))},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "self_role_change"


async def test_role_manager_cannot_grant_more_than_they_hold(client, make_user, db, company):
    # A delegated admin who can manage roles but holds nothing else.
    role = Role(company_id=company.id, name="Role Admin", slug="role_admin", is_system=False)
    db.add(role)
    await db.flush()
    for key in ("role.manage", "role.read", "user.read"):
        permission_id = await db.scalar(select(Permission.id).where(Permission.key == key))
        db.add(RolePermission(role_id=role.id, permission_id=permission_id))
    await db.commit()

    await make_user("delegate@eranova.co.ke", role="role_admin")
    target = await make_user("victim@eranova.co.ke")
    csrf = await login(client, "delegate@eranova.co.ke")

    response = await client.post(
        f"/api/v1/users/{target.id}/roles",
        json={"role_id": str(await _role_id(db, "super_admin"))},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_exceeds_authority"
    assert await db.scalar(select(UserRole.id).where(UserRole.user_id == target.id)) is None

    denied = await db.scalar(
        select(AuditLog).where(
            AuditLog.action == "role.assignment.create", AuditLog.outcome == "denied"
        )
    )
    assert denied is not None


async def test_last_active_super_admin_cannot_be_removed(client, make_user, db, company):
    # An unlocked custom role with every permission can manage Super Admin assignments.
    full = Role(company_id=company.id, name="Deputy", slug="deputy", is_system=False)
    db.add(full)
    await db.flush()
    for permission_id in await db.scalars(select(Permission.id)):
        db.add(RolePermission(role_id=full.id, permission_id=permission_id))
    await db.commit()

    await make_user("deputy@eranova.co.ke", role="deputy")
    owner = await make_user("owner@eranova.co.ke", role="super_admin")
    second = await make_user("second@eranova.co.ke", role="super_admin")
    csrf = await login(client, "deputy@eranova.co.ke")
    headers = {"X-CSRF-Token": csrf}

    second_assignment = await db.scalar(select(UserRole.id).where(UserRole.user_id == second.id))
    removed = await client.delete(
        f"/api/v1/users/{second.id}/roles/{second_assignment}", headers=headers
    )
    assert removed.status_code == 204

    owner_assignment = await db.scalar(select(UserRole.id).where(UserRole.user_id == owner.id))
    blocked = await client.delete(
        f"/api/v1/users/{owner.id}/roles/{owner_assignment}", headers=headers
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "last_super_admin"


async def test_scopes_for_unbuilt_modules_are_rejected(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    target = await make_user("pm@eranova.co.ke")
    csrf = await login(client, "root@eranova.co.ke")
    response = await client.post(
        f"/api/v1/users/{target.id}/roles",
        json={
            "role_id": str(await _role_id(db, "product_manager")),
            "scope_type": "product",
            "scope_id": str(uuid.uuid4()),
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "scope_not_available"


async def test_user_without_user_read_cannot_list_users(client, make_user):
    await make_user("own@eranova.co.ke", role="employee")
    await make_user("someone@eranova.co.ke")
    await login(client, "own@eranova.co.ke")
    assert (await client.get("/api/v1/users")).status_code == 403


async def test_user_list_for_company_reader(client, make_user):
    await make_user("exec@eranova.co.ke", role="executive", full_name="Exec")
    await make_user("dev@eranova.co.ke", full_name="Dev")
    await login(client, "exec@eranova.co.ke")
    response = await client.get("/api/v1/users", params={"q": "dev"})
    assert response.status_code == 200
    assert [u["email"] for u in response.json()["items"]] == ["dev@eranova.co.ke"]
    assert "password_hash" not in response.text
