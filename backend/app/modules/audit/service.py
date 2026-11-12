import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redaction import redact
from app.core.request_meta import RequestMeta
from app.modules.audit.models import ActorType, AuditLog, AuditOutcome


async def record_event(
    session: AsyncSession,
    *,
    action: str,
    outcome: AuditOutcome,
    meta: RequestMeta,
    actor_type: ActorType = ActorType.USER,
    actor_user_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Stage an audit event in the caller's transaction. The caller commits."""
    event = AuditLog(
        action=action,
        outcome=outcome,
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        company_id=company_id,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
        correlation_id=meta.correlation_id,
        details=redact(details or {}),
    )
    session.add(event)
    await session.flush()
    return event


async def list_events(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    limit: int,
    offset: int,
    action: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> tuple[list[AuditLog], int]:
    conditions = [AuditLog.company_id == company_id]
    if action:
        conditions.append(AuditLog.action == action)
    if actor_user_id:
        conditions.append(AuditLog.actor_user_id == actor_user_id)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if since:
        conditions.append(AuditLog.created_at >= since)
    if until:
        conditions.append(AuditLog.created_at < until)

    total = await session.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    rows = await session.scalars(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0
