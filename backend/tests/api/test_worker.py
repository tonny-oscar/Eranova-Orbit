from datetime import date, timedelta

from sqlalchemy import func, select

from app import worker
from app.modules.notifications.models import Notification
from tests.conftest import login


async def test_reminders_are_sent_once_per_day(client, make_user, db):
    owner = await make_user("sales@eranova.co.ke", role="super_admin")
    h = {"X-CSRF-Token": await login(client, "sales@eranova.co.ke")}
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    lead = await client.post(
        "/api/v1/leads",
        json={
            "full_name": "Amina Otieno",
            "email": "amina@hotel.example",
            "owner_user_id": str(owner.id),
            "next_follow_up": yesterday,
        },
        headers=h,
    )
    assert lead.status_code == 201, lead.text
    project = (await client.post("/api/v1/projects", json={"name": "Launch"}, headers=h)).json()
    await client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": "Ship it",
            "assignee_user_id": str(owner.id),
            "due_date": yesterday,
        },
        headers=h,
    )

    for _ in range(2):
        await worker.follow_up_reminders(db)
        await worker.task_due_reminders(db)

    kinds = dict(
        (
            await db.execute(
                select(Notification.kind, func.count())
                .where(Notification.user_id == owner.id)
                .group_by(Notification.kind)
            )
        ).all()
    )
    assert kinds.get("lead.follow_up") == 1
    assert kinds.get("task.overdue") == 1
