from datetime import date, timedelta

from tests.conftest import login


async def test_leave_request_flow_with_manager_approval(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    manager = await make_user("manager@eranova.co.ke", full_name="Manager")
    staff = await make_user("staff@eranova.co.ke", full_name="Staff")
    root_h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    await client.put(
        f"/api/v1/employees/{staff.id}", json={"manager_user_id": str(manager.id)}, headers=root_h
    )

    staff_h = {"X-CSRF-Token": await login(client, "staff@eranova.co.ke")}
    start = date.today() + timedelta(days=10)
    r = await client.post(
        "/api/v1/leave-requests",
        json={
            "type": "annual",
            "start_date": str(start),
            "end_date": str(start + timedelta(days=2)),
            "reason": "Family",
        },
        headers=staff_h,
    )
    assert r.status_code == 201
    leave = r.json()
    assert leave["days"] == 3 and leave["status"] == "pending"
    overlap = await client.post(
        "/api/v1/leave-requests",
        json={
            "type": "sick",
            "start_date": str(start + timedelta(days=1)),
            "end_date": str(start + timedelta(days=1)),
        },
        headers=staff_h,
    )
    assert overlap.status_code == 409
    self_decide = await client.post(
        f"/api/v1/leave-requests/{leave['id']}/decision",
        json={"decision": "approved"},
        headers=staff_h,
    )
    assert self_decide.status_code == 403

    manager_h = {"X-CSRF-Token": await login(client, "manager@eranova.co.ke")}
    work = (await client.get("/api/v1/me/work")).json()
    assert [r["id"] for r in work["leave_to_approve"]] == [leave["id"]]
    decided = await client.post(
        f"/api/v1/leave-requests/{leave['id']}/decision",
        json={"decision": "approved", "note": "Enjoy"},
        headers=manager_h,
    )
    assert decided.json()["status"] == "approved"
    assert decided.json()["decided_by"]["name"] == "Manager"

    await login(client, "staff@eranova.co.ke")
    work = (await client.get("/api/v1/me/work")).json()
    assert work["leave_requests"][0]["status"] == "approved"
    assert work["unread_notifications"] >= 1


async def test_invalid_leave_dates_rejected(client, make_user):
    await make_user("staff@eranova.co.ke")
    h = {"X-CSRF-Token": await login(client, "staff@eranova.co.ke")}
    r = await client.post(
        "/api/v1/leave-requests",
        json={"type": "annual", "start_date": "2030-01-10", "end_date": "2030-01-01"},
        headers=h,
    )
    assert r.status_code == 422


async def test_attendance_is_self_service_and_visible_to_hr(client, make_user):
    await make_user("hr@eranova.co.ke", role="hr")
    await make_user("staff@eranova.co.ke", full_name="Staff")
    staff_h = {"X-CSRF-Token": await login(client, "staff@eranova.co.ke")}

    assert (await client.post("/api/v1/attendance/check-out", headers=staff_h)).status_code == 400
    r = await client.post("/api/v1/attendance/check-in", json={"note": "Office"}, headers=staff_h)
    assert r.status_code == 201
    assert (
        await client.post("/api/v1/attendance/check-in", json={}, headers=staff_h)
    ).status_code == 409
    out = await client.post("/api/v1/attendance/check-out", headers=staff_h)
    assert out.json()["check_out_at"]
    assert len((await client.get("/api/v1/attendance")).json()) == 1
    assert (await client.get("/api/v1/attendance", params={"team": True})).status_code == 403

    await login(client, "hr@eranova.co.ke")
    team = (await client.get("/api/v1/attendance", params={"team": True})).json()
    assert [a["person"]["name"] for a in team] == ["Staff"]


async def test_my_work_lists_assigned_and_reviewable_tasks(client, make_user):
    await make_user("lead@eranova.co.ke", role="super_admin")
    dev = await make_user("dev@eranova.co.ke", role="developer")
    lead_h = {"X-CSRF-Token": await login(client, "lead@eranova.co.ke")}
    project = (
        await client.post("/api/v1/projects", json={"name": "Portal project"}, headers=lead_h)
    ).json()
    task = (
        await client.post(
            "/api/v1/tasks",
            json={
                "project_id": project["id"],
                "title": "Portal task",
                "assignee_user_id": str(dev.id),
            },
            headers=lead_h,
        )
    ).json()

    dev_h = {"X-CSRF-Token": await login(client, "dev@eranova.co.ke")}
    assert [t["title"] for t in (await client.get("/api/v1/me/work")).json()["open_tasks"]] == [
        "Portal task"
    ]
    await client.post(
        f"/api/v1/tasks/{task['id']}/transition", json={"to": "in_progress"}, headers=dev_h
    )
    await client.post(
        f"/api/v1/tasks/{task['id']}/transition", json={"to": "submitted"}, headers=dev_h
    )

    await login(client, "lead@eranova.co.ke")
    assert [
        t["title"] for t in (await client.get("/api/v1/me/work")).json()["awaiting_my_review"]
    ] == ["Portal task"]
