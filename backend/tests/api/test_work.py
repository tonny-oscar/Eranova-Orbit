import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.modules.notifications.models import Notification
from tests.conftest import login


async def _project(client, h, **extra):
    r = await client.post(
        "/api/v1/projects", json={"name": "ShulePoa v2", "status": "active"} | extra, headers=h
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _task(client, h, project_id, **extra):
    r = await client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Build fee module"} | extra,
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_project_creation_with_members_and_milestones(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin", full_name="Root")
    dev = await make_user("dev@eranova.co.ke", full_name="Dev")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    project = await _project(client, h)
    assert project["manager"]["name"] == "Root"
    assert [m["role_label"] for m in project["members"]] == ["Project manager"]

    r = await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": str(dev.id), "role_label": "Developer"},
        headers=h,
    )
    assert len(r.json()["members"]) == 2
    r = await client.post(
        f"/api/v1/projects/{project['id']}/milestones",
        json={"title": "Beta", "due_date": "2027-03-01"},
        headers=h,
    )
    assert r.json()["milestones"][0]["title"] == "Beta"
    dup = await client.post("/api/v1/projects", json={"name": "shulepoa v2"}, headers=h)
    assert dup.status_code == 409


async def test_full_review_lifecycle_with_notifications(client, make_user, db):
    await make_user("lead@eranova.co.ke", role="super_admin", full_name="Lead")
    dev = await make_user("dev@eranova.co.ke", role="developer", full_name="Dev")
    lead_h = {"X-CSRF-Token": await login(client, "lead@eranova.co.ke")}
    project = await _project(client, lead_h)
    task = await _task(client, lead_h, project["id"], assignee_user_id=str(dev.id))
    assert task["status"] == "assigned"
    assert (
        await db.scalar(select(Notification.kind).where(Notification.user_id == dev.id))
        == "task.assigned"
    )

    dev_h = {"X-CSRF-Token": await login(client, "dev@eranova.co.ke")}
    detail = (await client.get(f"/api/v1/tasks/{task['id']}")).json()
    assert "in_progress" in detail["allowed_transitions"]
    assert "under_review" not in detail["allowed_transitions"]
    assert (
        await client.post(
            f"/api/v1/tasks/{task['id']}/transition", json={"to": "in_progress"}, headers=dev_h
        )
    ).status_code == 200
    r = await client.post(
        f"/api/v1/tasks/{task['id']}/transition",
        json={"to": "submitted", "note": "Ready for review"},
        headers=dev_h,
    )
    assert r.json()["status"] == "submitted"
    assert r.json()["comments"][0]["body"] == "Ready for review"

    # The assignee can never review their own work, even with approve rights.
    self_review = await client.post(
        f"/api/v1/tasks/{task['id']}/review", json={"decision": "approved"}, headers=dev_h
    )
    assert self_review.status_code == 403

    lead_h = {"X-CSRF-Token": await login(client, "lead@eranova.co.ke")}
    no_comment = await client.post(
        f"/api/v1/tasks/{task['id']}/review",
        json={"decision": "revision_requested"},
        headers=lead_h,
    )
    assert no_comment.status_code == 400
    r = await client.post(
        f"/api/v1/tasks/{task['id']}/review",
        json={"decision": "revision_requested", "comment": "Add tests"},
        headers=lead_h,
    )
    assert r.json()["status"] == "revision_requested"

    dev_h = {"X-CSRF-Token": await login(client, "dev@eranova.co.ke")}
    await client.post(
        f"/api/v1/tasks/{task['id']}/transition", json={"to": "in_progress"}, headers=dev_h
    )
    await client.post(
        f"/api/v1/tasks/{task['id']}/transition", json={"to": "submitted"}, headers=dev_h
    )

    lead_h = {"X-CSRF-Token": await login(client, "lead@eranova.co.ke")}
    await client.post(
        f"/api/v1/tasks/{task['id']}/review",
        json={"decision": "approved", "comment": "Great"},
        headers=lead_h,
    )
    done = await client.post(
        f"/api/v1/tasks/{task['id']}/transition", json={"to": "completed"}, headers=lead_h
    )
    body = done.json()
    assert body["status"] == "completed" and body["completed_at"]
    assert [r["decision"] for r in body["reviews"]] == ["approved", "revision_requested"]
    assert any(e["kind"] == "review" for e in body["events"])
    kinds = set(await db.scalars(select(Notification.kind).where(Notification.user_id == dev.id)))
    assert {"task.assigned", "task.revision_requested", "task.approved", "task.completed"} <= kinds


async def test_links_are_evidence_not_completion(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    project = await _project(client, h)
    task = await _task(client, h, project["id"])
    r = await client.post(
        f"/api/v1/tasks/{task['id']}/links",
        json={
            "kind": "github_pr",
            "url": "https://github.com/eranova/shulepoa/pull/12",
            "title": "PR #12",
        },
        headers=h,
    )
    assert r.json()["links"][0]["kind"] == "github_pr"
    assert r.json()["status"] == "created"


async def test_dependencies_block_start_and_prevent_cycles(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    dev = await make_user("dev@eranova.co.ke", role="developer")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    project = await _project(client, h)
    first = await _task(client, h, project["id"], title="Design schema")
    second = await _task(client, h, project["id"], title="Build API", assignee_user_id=str(dev.id))

    assert (
        await client.post(
            f"/api/v1/tasks/{second['id']}/dependencies",
            json={"depends_on_task_id": first["id"]},
            headers=h,
        )
    ).status_code == 201
    cycle = await client.post(
        f"/api/v1/tasks/{first['id']}/dependencies",
        json={"depends_on_task_id": second["id"]},
        headers=h,
    )
    assert cycle.status_code == 400

    dev_h = {"X-CSRF-Token": await login(client, "dev@eranova.co.ke")}
    blocked = await client.post(
        f"/api/v1/tasks/{second['id']}/transition", json={"to": "in_progress"}, headers=dev_h
    )
    assert blocked.status_code == 409
    assert "Design schema" in blocked.json()["error"]["message"]


async def test_project_scoped_access_and_overdue_counts(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    mine = await _project(client, h, name="Mine")
    other = await _project(client, h, name="Other")
    await _task(client, h, mine["id"], title="Late", due_date=str(date.today() - timedelta(days=2)))
    await _task(client, h, other["id"], title="Hidden")

    await make_user(
        "pm@eranova.co.ke",
        role="project_manager",
        scope_type="project",
        scope_id=uuid.UUID(mine["id"]),
    )
    await login(client, "pm@eranova.co.ke")
    projects = (await client.get("/api/v1/projects")).json()["items"]
    assert [p["name"] for p in projects] == ["Mine"]
    assert projects[0]["tasks"]["overdue"] == 1
    titles = [t["title"] for t in (await client.get("/api/v1/tasks")).json()["items"]]
    assert titles == ["Late"]
    assert (await client.get(f"/api/v1/projects/{other['id']}")).status_code == 404


async def test_subtasks_stay_in_project(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    a = await _project(client, h, name="Alpha")
    b = await _project(client, h, name="Bravo")
    parent = await _task(client, h, a["id"])
    bad = await client.post(
        "/api/v1/tasks",
        json={"project_id": b["id"], "title": "Sub", "parent_task_id": parent["id"]},
        headers=h,
    )
    assert bad.status_code == 400
    ok = await _task(client, h, a["id"], title="Subtask", parent_task_id=parent["id"])
    detail = (await client.get(f"/api/v1/tasks/{parent['id']}")).json()
    assert [s["id"] for s in detail["subtasks"]] == [ok["id"]]


async def test_notifications_api(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    dev = await make_user("dev@eranova.co.ke", role="developer")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    project = await _project(client, h)
    await _task(client, h, project["id"], assignee_user_id=str(dev.id))

    dev_h = {"X-CSRF-Token": await login(client, "dev@eranova.co.ke")}
    page = (await client.get("/api/v1/notifications")).json()
    assert page["unread"] == 1
    await client.post("/api/v1/notifications/read-all", headers=dev_h)
    assert (await client.get("/api/v1/notifications")).json()["unread"] == 0
