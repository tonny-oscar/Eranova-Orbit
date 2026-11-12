import uuid

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.authorization.models import Role
from tests.conftest import login


async def _department(client, csrf, name, **extra):
    response = await client.post(
        "/api/v1/departments", json={"name": name} | extra, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_super_admin_manages_departments(client, make_user, db):
    head = await make_user("head@eranova.co.ke", full_name="Head")
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")

    engineering = await _department(client, csrf, "Engineering", head_user_id=str(head.id))
    assert engineering["head"]["email"] == "head@eranova.co.ke"
    assert engineering["member_count"] == 0

    duplicate = await client.post(
        "/api/v1/departments", json={"name": "engineering"}, headers={"X-CSRF-Token": csrf}
    )
    assert duplicate.status_code == 409

    renamed = await client.patch(
        f"/api/v1/departments/{engineering['id']}",
        json={"name": "Product Engineering"},
        headers={"X-CSRF-Token": csrf},
    )
    assert renamed.json()["name"] == "Product Engineering"
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "department.update"))


async def test_hr_cannot_restructure_departments(client, make_user):
    await make_user("hr@eranova.co.ke", role="hr")
    csrf = await login(client, "hr@eranova.co.ke")
    response = await client.post(
        "/api/v1/departments", json={"name": "Shadow"}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 403


async def test_employee_profile_upsert_and_validation(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    manager = await make_user("lead@eranova.co.ke", full_name="Lead")
    person = await make_user("dev@eranova.co.ke", full_name="Dev")
    csrf = await login(client, "root@eranova.co.ke")
    headers = {"X-CSRF-Token": csrf}
    engineering = await _department(client, csrf, "Engineering")

    empty = await client.get(f"/api/v1/employees/{person.id}")
    assert empty.status_code == 200 and empty.json()["has_profile"] is False

    saved = await client.put(
        f"/api/v1/employees/{person.id}",
        json={
            "department_id": engineering["id"],
            "job_title": "Backend Developer",
            "manager_user_id": str(manager.id),
            "employment_type": "full_time",
            "start_date": "2026-02-01",
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["department"]["name"] == "Engineering"
    assert body["manager"]["email"] == "lead@eranova.co.ke"
    assert body["has_profile"] is True

    own_manager = await client.put(
        f"/api/v1/employees/{person.id}",
        json={"manager_user_id": str(person.id)},
        headers=headers,
    )
    assert own_manager.status_code == 400

    # lead -> dev would make dev manage their own manager: a loop.
    loop = await client.put(
        f"/api/v1/employees/{manager.id}",
        json={"manager_user_id": str(person.id)},
        headers=headers,
    )
    assert loop.status_code == 400
    assert "loop" in loop.json()["error"]["message"]

    departments = await client.get("/api/v1/departments")
    assert departments.json()[0]["member_count"] == 1
    event = await db.scalar(select(AuditLog).where(AuditLog.action == "employee.update"))
    assert event.details["created"] is True


async def test_department_scoped_manager_sees_only_their_department(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    csrf = await login(client, "root@eranova.co.ke")
    engineering = await _department(client, csrf, "Engineering")
    sales = await _department(client, csrf, "Sales")
    dev = await make_user("dev@eranova.co.ke", full_name="Dev")
    seller = await make_user("seller@eranova.co.ke", full_name="Seller")
    for user, dept in ((dev, engineering), (seller, sales)):
        await client.put(
            f"/api/v1/employees/{user.id}",
            json={"department_id": dept["id"]},
            headers={"X-CSRF-Token": csrf},
        )

    await make_user(
        "eng.lead@eranova.co.ke",
        role="department_manager",
        scope_type="department",
        scope_id=uuid.UUID(engineering["id"]),
        full_name="Eng Lead",
    )
    lead_csrf = await login(client, "eng.lead@eranova.co.ke")

    employees = await client.get("/api/v1/employees")
    assert [e["user"]["email"] for e in employees.json()["items"]] == ["dev@eranova.co.ke"]
    users = await client.get("/api/v1/users")
    assert {u["email"] for u in users.json()["items"]} == {
        "dev@eranova.co.ke",
        "eng.lead@eranova.co.ke",
    }
    assert (await client.get(f"/api/v1/employees/{seller.id}")).status_code == 404

    edit = await client.put(
        f"/api/v1/employees/{dev.id}",
        json={"department_id": engineering["id"], "job_title": "Senior Developer"},
        headers={"X-CSRF-Token": lead_csrf},
    )
    assert edit.status_code == 200
    poach = await client.put(
        f"/api/v1/employees/{dev.id}",
        json={"department_id": sales["id"]},
        headers={"X-CSRF-Token": lead_csrf},
    )
    assert poach.status_code == 403


async def test_department_scope_assignment_is_validated(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    target = await make_user("lead@eranova.co.ke")
    csrf = await login(client, "root@eranova.co.ke")
    engineering = await _department(client, csrf, "Engineering")
    role_id = await db.scalar(select(Role.id).where(Role.slug == "department_manager"))

    bogus = await client.post(
        f"/api/v1/users/{target.id}/roles",
        json={"role_id": str(role_id), "scope_type": "department", "scope_id": str(uuid.uuid4())},
        headers={"X-CSRF-Token": csrf},
    )
    assert bogus.status_code == 400
    ok = await client.post(
        f"/api/v1/users/{target.id}/roles",
        json={"role_id": str(role_id), "scope_type": "department", "scope_id": engineering["id"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert ok.status_code == 201


async def test_own_scope_employee_sees_only_self(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    await make_user("someone@eranova.co.ke")
    me = await make_user("me@eranova.co.ke", role="auditor", scope_type="own")
    await login(client, "me@eranova.co.ke")
    employees = await client.get("/api/v1/employees")
    assert [e["user"]["id"] for e in employees.json()["items"]] == [str(me.id)]
