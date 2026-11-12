from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.authorization.models import Permission, Role, RolePermission
from app.modules.identity.models import UserSession
from tests.conftest import DEFAULT_PASSWORD, login

USERS = "/api/v1/users"
ROLES = "/api/v1/roles"


async def _custom_role(db, company, slug: str, keys: list[str]) -> Role:
    role = Role(company_id=company.id, name=slug.title(), slug=slug, is_system=False)
    db.add(role)
    await db.flush()
    for key in keys:
        permission_id = await db.scalar(select(Permission.id).where(Permission.key == key))
        db.add(RolePermission(role_id=role.id, permission_id=permission_id))
    await db.commit()
    return role


async def test_admin_creates_user_who_must_change_password(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")

    created = await client.post(
        USERS,
        json={"email": "New.Hire@Eranova.co.ke", "full_name": "New Hire"},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    temporary = body["temporary_password"]
    assert len(temporary) == 16
    assert body["user"]["email"] == "new.hire@eranova.co.ke"
    assert body["user"]["must_change_password"] is True
    assert created.headers["cache-control"] == "no-store"
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "user.create"))
    assert temporary not in str(audit.details)

    new_csrf = await login(client, "new.hire@eranova.co.ke", temporary)
    me = await client.get("/api/v1/auth/me")
    assert me.json()["user"]["must_change_password"] is True
    blocked = await client.get("/api/v1/products")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": temporary, "new_password": "my-own-long-passphrase"},
        headers={"X-CSRF-Token": new_csrf},
    )
    assert changed.status_code == 204
    assert (await client.get("/api/v1/auth/me")).json()["user"]["must_change_password"] is False


async def test_user_list_includes_role_names_and_filters(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin", full_name="Root")
    await make_user("dev@eranova.co.ke", role="developer", full_name="Dev")
    await login(client, "root@eranova.co.ke")

    response = await client.get(USERS, params={"q": "dev"})
    assert [(u["email"], u["role_names"]) for u in response.json()["items"]] == [
        ("dev@eranova.co.ke", ["Developer"])
    ]
    disabled = await client.get(USERS, params={"status": "disabled"})
    assert disabled.json()["total"] == 0


async def test_disable_user_revokes_sessions_and_blocks_login(app, client, make_user, db):
    from httpx import ASGITransport, AsyncClient

    await make_user("root@eranova.co.ke", role="super_admin")
    target = await make_user("leaver@eranova.co.ke", role="developer")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as other:
        await login(other, "leaver@eranova.co.ke")
        csrf = await login(client, "root@eranova.co.ke")

        response = await client.patch(
            f"{USERS}/{target.id}", json={"status": "disabled"}, headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "disabled"
        assert (await other.get("/api/v1/auth/me")).status_code == 401

    relogin = await client.post(
        "/api/v1/auth/login", json={"email": "leaver@eranova.co.ke", "password": DEFAULT_PASSWORD}
    )
    assert relogin.status_code == 401
    active = await db.scalar(
        select(UserSession.id).where(
            UserSession.user_id == target.id, UserSession.revoked_at.is_(None)
        )
    )
    assert active is None


async def test_admin_reset_password_issues_new_temporary_password(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    target = await make_user("forgot@eranova.co.ke", role="developer")
    csrf = await login(client, "root@eranova.co.ke")

    response = await client.post(
        f"{USERS}/{target.id}/reset-password", headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200
    temporary = response.json()["temporary_password"]
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "forgot@eranova.co.ke", "password": DEFAULT_PASSWORD},
        )
    ).status_code == 401
    await login(client, "forgot@eranova.co.ke", temporary)


async def test_delegated_admin_cannot_take_over_more_privileged_account(
    client, make_user, db, company
):
    await _custom_role(
        db, company, "user_admin", ["user.read", "user.create", "user.update", "user.manage"]
    )
    await make_user("helpdesk@eranova.co.ke", role="user_admin")
    owner = await make_user("owner@eranova.co.ke", role="super_admin")
    junior = await make_user("intern@eranova.co.ke")
    csrf = await login(client, "helpdesk@eranova.co.ke")

    takeover = await client.post(
        f"{USERS}/{owner.id}/reset-password", headers={"X-CSRF-Token": csrf}
    )
    assert takeover.status_code == 403
    assert takeover.json()["error"]["code"] == "target_more_privileged"
    disable = await client.patch(
        f"{USERS}/{owner.id}", json={"status": "disabled"}, headers={"X-CSRF-Token": csrf}
    )
    assert disable.status_code == 403

    allowed = await client.post(
        f"{USERS}/{junior.id}/reset-password", headers={"X-CSRF-Token": csrf}
    )
    assert allowed.status_code == 200
    denied_events = await db.scalars(
        select(AuditLog.action).where(
            AuditLog.outcome == "denied", AuditLog.resource_id == str(owner.id)
        )
    )
    assert set(denied_events) == {"user.password.reset", "user.status.change"}


async def test_cannot_disable_self_or_last_super_admin(client, make_user, db, company):
    admin = await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    self_disable = await client.patch(
        f"{USERS}/{admin.id}", json={"status": "disabled"}, headers={"X-CSRF-Token": csrf}
    )
    assert self_disable.status_code == 403

    all_keys = [k for k in await db.scalars(select(Permission.key))]
    await _custom_role(db, company, "deputy", all_keys)
    await make_user("deputy@eranova.co.ke", role="deputy")
    deputy_csrf = await login(client, "deputy@eranova.co.ke")
    last = await client.patch(
        f"{USERS}/{admin.id}", json={"status": "disabled"}, headers={"X-CSRF-Token": deputy_csrf}
    )
    assert last.status_code == 409
    assert last.json()["error"]["code"] == "last_super_admin"


async def test_custom_role_lifecycle(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    headers = {"X-CSRF-Token": csrf}

    created = await client.post(
        ROLES,
        json={
            "name": "Content Editor",
            "description": "Edits docs",
            "permissions": ["document.read"],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    role = created.json()
    assert role["slug"] == "content_editor" and role["is_system"] is False

    duplicate = await client.post(ROLES, json={"name": "content editor"}, headers=headers)
    assert duplicate.status_code == 409

    unknown = await client.post(
        ROLES, json={"name": "Weird", "permissions": ["nope.read"]}, headers=headers
    )
    assert unknown.status_code == 400

    updated = await client.patch(
        f"{ROLES}/{role['id']}",
        json={"permissions": ["document.read", "document.update"]},
        headers=headers,
    )
    assert updated.json()["permissions"] == ["document.read", "document.update"]
    event = await db.scalar(select(AuditLog).where(AuditLog.action == "role.update"))
    assert event.details["permissions_added"] == ["document.update"]

    deleted = await client.delete(f"{ROLES}/{role['id']}", headers=headers)
    assert deleted.status_code == 204


async def test_locked_and_system_roles_are_protected(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    headers = {"X-CSRF-Token": csrf}
    super_admin_id = await db.scalar(select(Role.id).where(Role.slug == "super_admin"))
    developer_id = await db.scalar(select(Role.id).where(Role.slug == "developer"))

    locked = await client.patch(
        f"{ROLES}/{super_admin_id}", json={"permissions": []}, headers=headers
    )
    assert locked.status_code == 403
    assert locked.json()["error"]["code"] == "role_locked"

    starter_edit = await client.patch(
        f"{ROLES}/{developer_id}", json={"description": "Builds products"}, headers=headers
    )
    assert starter_edit.status_code == 200
    starter_delete = await client.delete(f"{ROLES}/{developer_id}", headers=headers)
    assert starter_delete.status_code == 403


async def test_role_editor_cannot_grant_permissions_they_lack(client, make_user, db, company):
    await _custom_role(db, company, "role_editor", ["role.read", "role.create", "role.update"])
    await make_user("editor@eranova.co.ke", role="role_editor")
    csrf = await login(client, "editor@eranova.co.ke")

    response = await client.post(
        ROLES,
        json={"name": "Sneaky", "permissions": ["invoice.approve"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_exceeds_authority"
