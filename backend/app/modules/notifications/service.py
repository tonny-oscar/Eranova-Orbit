import uuid
from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.modules.notifications.models import Notification


async def notify(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    user_ids: Iterable[uuid.UUID | None],
    kind: str,
    title: str,
    body: str = "",
    link: str | None = None,
    exclude: uuid.UUID | None = None,
) -> None:
    """Stage notifications in the caller's transaction (deduplicated, actor excluded)."""
    for user_id in {u for u in user_ids if u and u != exclude}:
        session.add(
            Notification(
                company_id=company_id,
                user_id=user_id,
                kind=kind,
                title=title[:200],
                body=body,
                link=link,
            )
        )


async def list_for(
    session: AsyncSession, user_id: uuid.UUID, *, unread_only: bool, limit: int, offset: int
) -> tuple[list[Notification], int, int]:
    conditions = [Notification.user_id == user_id]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    total = await session.scalar(select(func.count()).select_from(Notification).where(*conditions))
    unread = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    rows = await session.scalars(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0, unread or 0


async def mark_read(
    session: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID | None = None
) -> None:
    conditions = [Notification.user_id == user_id, Notification.read_at.is_(None)]
    if notification_id:
        conditions.append(Notification.id == notification_id)
    await session.execute(update(Notification).where(*conditions).values(read_at=utc_now()))
    await session.commit()
