"""Background worker: scheduled syncs, reminders and retention.

    python -m app.worker          Run forever (Render background worker)
    python -m app.worker --once   Run one cycle and exit (cron / tests)

State lives in PostgreSQL (last_sync_at, reminder markers), so the worker is
safe to restart and to run as a single instance alongside any number of API
instances.
"""

import argparse
import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import utc_now
from app.db.session import dispose_engine, get_sessionmaker
from app.modules.crm.models import Lead
from app.modules.integrations import service as integration_service
from app.modules.marketing import service as marketing_service
from app.modules.notifications.models import Notification
from app.modules.notifications.service import notify
from app.modules.reports import service as report_service
from app.modules.work.models import Task
from app.modules.work.service import OPEN_STATUSES

logger = logging.getLogger("app.worker")
CYCLE_SECONDS = 60
_JOBS: list = []


def job(func):
    _JOBS.append(func)
    return func


@job
async def sync_due_integrations(session) -> None:
    for connection in await integration_service.due_connections(session):
        run = await integration_service.run_sync(session, connection, trigger="scheduled")
        logger.info(
            "integration synced", extra={"connection": connection.name, "status": run.status}
        )


REMINDER_REPEAT = timedelta(hours=20)


async def _already_notified(session, user_id, kind: str, link: str) -> bool:
    return bool(
        await session.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.kind == kind,
                Notification.link == link,
                Notification.created_at >= utc_now() - REMINDER_REPEAT,
            )
        )
    )


@job
async def follow_up_reminders(session) -> None:
    today = date.today()
    leads = await session.scalars(
        select(Lead).where(
            Lead.next_follow_up <= today,
            Lead.owner_user_id.is_not(None),
            Lead.converted_customer_id.is_(None),
        )
    )
    for lead in leads:
        link = f"/app/leads/{lead.id}"
        if not await _already_notified(session, lead.owner_user_id, "lead.follow_up", link):
            await notify(
                session,
                company_id=lead.company_id,
                user_ids=[lead.owner_user_id],
                kind="lead.follow_up",
                title=f"Follow up with {lead.full_name}",
                body=f"Scheduled for {lead.next_follow_up}",
                link=link,
            )
    await session.commit()


@job
async def task_due_reminders(session) -> None:
    today = date.today()
    tasks = await session.scalars(
        select(Task).where(
            Task.status.in_(OPEN_STATUSES),
            Task.assignee_user_id.is_not(None),
            Task.due_date.is_not(None),
            Task.due_date <= today + timedelta(days=1),
        )
    )
    for task in tasks:
        link = f"/app/tasks/{task.id}"
        kind = "task.overdue" if task.due_date < today else "task.due_soon"
        if not await _already_notified(session, task.assignee_user_id, kind, link):
            await notify(
                session,
                company_id=task.company_id,
                user_ids=[task.assignee_user_id],
                kind=kind,
                title=f"{'Overdue' if kind == 'task.overdue' else 'Due tomorrow'}: {task.title}",
                link=link,
            )
    await session.commit()


@job
async def scheduled_content_reminders(session) -> None:
    """Without a connected publishing provider nothing is auto-published, so
    remind the author when a scheduled slot passes unconfirmed."""
    for item in await marketing_service.overdue_scheduled(session):
        if not item.author_user_id:
            continue
        link = f"/app/marketing/content/{item.id}"
        if not await _already_notified(session, item.author_user_id, "content.publish_due", link):
            await notify(
                session,
                company_id=item.company_id,
                user_ids=[item.author_user_id],
                kind="content.publish_due",
                title=f"Scheduled time passed: {item.title}",
                body="Publish it and record the link, or reschedule.",
                link=link,
            )
    await session.commit()


@job
async def scheduled_reports(session) -> None:
    for schedule in await report_service.due_schedules(session):
        delivered = await report_service.run_schedule(session, schedule)
        logger.info(
            "scheduled report delivered", extra={"schedule": schedule.name, "recipients": delivered}
        )


@job
async def retention(session) -> None:
    removed = await integration_service.purge_old_checks(session)
    if removed:
        logger.info("purged old uptime checks", extra={"rows": removed})


async def run_cycle() -> None:
    for func in _JOBS:
        async with get_sessionmaker()() as session:
            try:
                await func(session)
            except Exception:
                logger.exception("worker job failed", extra={"job": func.__name__})


async def main(once: bool) -> None:
    configure_logging(get_settings().log_level)
    try:
        while True:
            await run_cycle()
            if once:
                return
            await asyncio.sleep(CYCLE_SECONDS)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    asyncio.run(main(parser.parse_args().once))
