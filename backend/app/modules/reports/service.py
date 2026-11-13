"""Report runs, scheduled delivery and exports."""

import uuid
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.db.base import utc_now
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed
from app.modules.authorization.service import load_principal
from app.modules.company.models import Company
from app.modules.crm.service import lookup
from app.modules.identity.models import User, UserStatus
from app.modules.notifications.service import notify
from app.modules.products.service import product_exists
from app.modules.reports.generators import REPORTS, Period, _can, generate
from app.modules.reports.models import ReportRun, ReportSchedule

MAX_RANGE_DAYS = 366
DELIVERY_HOUR = 6


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class ScheduleIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    report_key: str = Field(max_length=40)
    frequency: Literal["weekly", "monthly"]
    range_days: int = Field(default=30, ge=1, le=MAX_RANGE_DAYS)
    product_id: uuid.UUID | None = None
    recipient_user_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class SchedulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    range_days: int | None = Field(default=None, ge=1, le=MAX_RANGE_DAYS)
    recipient_user_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=50)
    active: bool | None = None


class ScheduleOut(BaseModel):
    id: uuid.UUID
    name: str
    report_key: str
    report_title: str
    frequency: str
    range_days: int
    product_id: uuid.UUID | None
    recipients: list[Ref]
    owner: Ref | None
    active: bool
    next_run_at: datetime
    last_run_at: datetime | None
    can_manage: bool


class RunSummary(BaseModel):
    id: uuid.UUID
    report_key: str
    title: str
    period_start: date
    period_end: date
    generated_at: datetime
    schedule_id: uuid.UUID | None


def resolve_period(start: date | None, end: date | None) -> Period:
    end = end or date.today()
    start = start or end - timedelta(days=29)
    if start > end:
        raise AppError("The start date must be on or before the end date.", code="invalid_range")
    if (end - start).days >= MAX_RANGE_DAYS:
        raise AppError("Reports cover at most one year.", code="invalid_range")
    return Period(start, end)


def report_allowed(principal: Principal, key: str) -> bool:
    report = REPORTS.get(key)
    if report is None or not _can(principal, "report.read"):
        return False
    return report.permission is None or _can(principal, report.permission)


def require_report(principal: Principal, key: str):
    if key not in REPORTS:
        raise NotFoundError("Report not found.")
    if not report_allowed(principal, key):
        raise PermissionDeniedError("You do not have access to the data in this report.")
    return REPORTS[key]


async def run_report(session, principal, key, period, product_id=None) -> dict:
    require_report(principal, key)
    if product_id and not await product_exists(session, principal.company_id, product_id):
        raise AppError("Product not found.", code="invalid_product")
    return jsonable_encoder(await generate(session, principal, key, period, product_id))


def flatten(report: dict) -> list[tuple[str, list[str], list[list]]]:
    """Report sections as (title, header, rows) tables for CSV/Excel."""
    tables = []
    for s in report["sections"]:
        if s["metrics"]:
            tables.append(
                (
                    s["title"],
                    ["Metric", "Value", "Unit"],
                    [[m["label"], m["value"], m.get("unit") or ""] for m in s["metrics"]],
                )
            )
        if s["columns"]:
            tables.append(
                (
                    s["title"] if not s["metrics"] else f"{s['title']} detail",
                    s["columns"],
                    s["rows"],
                )
            )
    return tables


async def record_report_export(session, actor: User, key: str, fmt: str, meta) -> None:
    await record_event(
        session,
        action="data.export",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="report",
        meta=meta,
        details={"dataset": f"report:{key}", "format": fmt},
    )
    await session.commit()


# --- Schedules ---------------------------------------------------------------------------------


def _advance(at: datetime, frequency: str, tz: ZoneInfo) -> datetime:
    local = at.astimezone(tz)
    if frequency == "weekly":
        nxt = local + timedelta(days=7)
    else:
        month = local.month % 12 + 1
        year = local.year + (local.month == 12)
        nxt = local.replace(year=year, month=month, day=min(local.day, 28))
    return nxt


async def _company_tz(session, company_id) -> ZoneInfo:
    name = await session.scalar(select(Company.timezone).where(Company.id == company_id))
    return ZoneInfo(name or "UTC")


async def first_run(session, company_id) -> datetime:
    tz = await _company_tz(session, company_id)
    now = utc_now().astimezone(tz)
    candidate = datetime.combine(now.date(), time(DELIVERY_HOUR), tzinfo=tz)
    return candidate if candidate > now else candidate + timedelta(days=1)


async def _check_recipients(session, company_id, user_ids, report_key) -> None:
    users = list(
        await session.scalars(
            select(User).where(
                User.id.in_(set(user_ids)),
                User.company_id == company_id,
                User.status == UserStatus.ACTIVE,
            )
        )
    )
    if len(users) != len(set(user_ids)):
        raise AppError("Every recipient must be an active user.", code="invalid_user")
    for user in users:
        if not report_allowed(await load_principal(session, user), report_key):
            raise AppError(
                f"{user.full_name} cannot open this report, so it cannot be sent to them.",
                code="recipient_not_permitted",
            )


def _can_manage(principal: Principal, s: ReportSchedule) -> bool:
    return s.owner_user_id == principal.user_id or is_allowed(
        principal, "report.manage", ResourceContext(company_id=s.company_id)
    )


async def list_schedules(session, principal) -> list[ReportSchedule]:
    cond = [ReportSchedule.company_id == principal.company_id]
    if not is_allowed(principal, "report.manage", ResourceContext(company_id=principal.company_id)):
        cond.append(
            or_(
                ReportSchedule.owner_user_id == principal.user_id,
                ReportSchedule.recipient_user_ids.any(principal.user_id),
            )
        )
    return list(
        await session.scalars(select(ReportSchedule).where(*cond).order_by(ReportSchedule.name))
    )


async def schedule_outs(session, principal, schedules) -> list[ScheduleOut]:
    users = await lookup(
        session,
        User,
        {u for s in schedules for u in s.recipient_user_ids} | {s.owner_user_id for s in schedules},
    )

    def ref(uid):
        u = users.get(uid)
        return Ref(id=u.id, name=u.full_name) if u else None

    return [
        ScheduleOut(
            id=s.id,
            name=s.name,
            report_key=s.report_key,
            report_title=REPORTS[s.report_key].title if s.report_key in REPORTS else s.report_key,
            frequency=s.frequency,
            range_days=s.range_days,
            product_id=s.product_id,
            recipients=[r for r in (ref(u) for u in s.recipient_user_ids) if r],
            owner=ref(s.owner_user_id),
            active=s.active,
            next_run_at=s.next_run_at,
            last_run_at=s.last_run_at,
            can_manage=_can_manage(principal, s),
        )
        for s in schedules
    ]


async def _get_schedule(session, principal, schedule_id) -> ReportSchedule:
    s = await session.scalar(
        select(ReportSchedule).where(
            ReportSchedule.id == schedule_id, ReportSchedule.company_id == principal.company_id
        )
    )
    if s is None or not _can_manage(principal, s):
        raise NotFoundError("Schedule not found.")
    return s


async def _audit(session, actor, action, schedule_id, meta, details=None):
    await record_event(
        session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="report_schedule",
        resource_id=schedule_id,
        meta=meta,
        details=details or {},
    )


async def create_schedule(session, actor, principal, payload: ScheduleIn, meta) -> ReportSchedule:
    require_report(principal, payload.report_key)
    if payload.product_id and not await product_exists(
        session, actor.company_id, payload.product_id
    ):
        raise AppError("Product not found.", code="invalid_product")
    await _check_recipients(
        session, actor.company_id, payload.recipient_user_ids, payload.report_key
    )
    s = ReportSchedule(
        company_id=actor.company_id,
        owner_user_id=actor.id,
        next_run_at=await first_run(session, actor.company_id),
        **{**payload.model_dump(), "recipient_user_ids": sorted(set(payload.recipient_user_ids))},
    )
    session.add(s)
    await session.flush()
    await _audit(
        session,
        actor,
        "report_schedule.create",
        s.id,
        meta,
        {"report": s.report_key, "recipients": len(s.recipient_user_ids)},
    )
    await session.commit()
    return s


async def update_schedule(session, actor, principal, schedule_id, payload: SchedulePatch, meta):
    s = await _get_schedule(session, principal, schedule_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("recipient_user_ids"):
        await _check_recipients(
            session, actor.company_id, changes["recipient_user_ids"], s.report_key
        )
        changes["recipient_user_ids"] = sorted(set(changes["recipient_user_ids"]))
    for field, value in changes.items():
        if value is None:
            raise AppError(
                f"{field.replace('_', ' ').title()} cannot be empty.", code="invalid_field"
            )
        setattr(s, field, value)
    if changes.get("active") and s.next_run_at < utc_now():
        s.next_run_at = await first_run(session, s.company_id)
    await _audit(session, actor, "report_schedule.update", s.id, meta, {"fields": sorted(changes)})
    await session.commit()
    await session.refresh(s)
    return s


async def delete_schedule(session, actor, principal, schedule_id, meta) -> None:
    s = await _get_schedule(session, principal, schedule_id)
    await _audit(session, actor, "report_schedule.delete", s.id, meta, {"name": s.name})
    await session.delete(s)
    await session.commit()


async def run_schedule(session, s: ReportSchedule) -> int:
    """Generate one snapshot per recipient using the recipient's own access."""
    end = date.today() - timedelta(days=1)
    period = Period(end - timedelta(days=s.range_days - 1), end)
    delivered = 0
    for user in await session.scalars(
        select(User).where(User.id.in_(s.recipient_user_ids), User.status == UserStatus.ACTIVE)
    ):
        principal = await load_principal(session, user)
        if not report_allowed(principal, s.report_key):
            continue
        data = jsonable_encoder(
            await generate(session, principal, s.report_key, period, s.product_id)
        )
        run = ReportRun(
            company_id=s.company_id,
            schedule_id=s.id,
            report_key=s.report_key,
            title=f"{s.name} ({period.start:%d %b} to {period.end:%d %b %Y})",
            recipient_user_id=user.id,
            period_start=period.start,
            period_end=period.end,
            data=data,
        )
        session.add(run)
        await session.flush()
        await notify(
            session,
            company_id=s.company_id,
            user_ids=[user.id],
            kind="report.delivered",
            title=f"Report ready: {run.title}",
            link=f"/app/reports/runs/{run.id}",
        )
        delivered += 1
    tz = await _company_tz(session, s.company_id)
    s.last_run_at = utc_now()
    nxt = s.next_run_at
    while nxt <= s.last_run_at:
        nxt = _advance(nxt, s.frequency, tz)
    s.next_run_at = nxt
    await session.commit()
    return delivered


async def due_schedules(session) -> list[ReportSchedule]:
    return list(
        await session.scalars(
            select(ReportSchedule).where(
                ReportSchedule.active.is_(True), ReportSchedule.next_run_at <= utc_now()
            )
        )
    )


async def my_runs(session, principal, limit=50) -> list[ReportRun]:
    return list(
        await session.scalars(
            select(ReportRun)
            .where(ReportRun.recipient_user_id == principal.user_id)
            .order_by(ReportRun.generated_at.desc())
            .limit(limit)
        )
    )


async def get_run(session, principal, run_id) -> ReportRun:
    run = await session.scalar(
        select(ReportRun).where(
            ReportRun.id == run_id, ReportRun.recipient_user_id == principal.user_id
        )
    )
    if run is None:
        raise NotFoundError("Report not found.")
    return run
