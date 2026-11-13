"""Employee portal: my work, leave requests and transparent attendance."""

import uuid
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_request_meta
from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.request_meta import RequestMeta
from app.db.base import utc_now
from app.db.session import get_db
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import is_allowed
from app.modules.company.models import Company
from app.modules.identity.models import User
from app.modules.notifications.service import list_for as list_notifications
from app.modules.notifications.service import notify
from app.modules.people.models import AttendanceRecord, EmployeeProfile, LeaveRequest
from app.modules.people.service import department_member_condition, employee_context
from app.modules.work import service as work_service
from app.modules.work.models import Project, Task, TaskStatus

router = APIRouter(tags=["portal"])

LeaveType = Literal["annual", "sick", "parental", "unpaid", "other"]


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class LeaveIn(BaseModel):
    type: LeaveType
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _ordered(self) -> "LeaveIn":
        if self.end_date < self.start_date:
            raise ValueError("The end date must be on or after the start date.")
        if (self.end_date - self.start_date).days > 365:
            raise ValueError("Leave requests cannot exceed one year.")
        return self


class LeaveDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=1000)


class LeaveOut(BaseModel):
    id: uuid.UUID
    person: Ref
    type: str
    start_date: date
    end_date: date
    days: int
    reason: str
    status: str
    decided_by: Ref | None
    decided_at: datetime | None
    decision_note: str | None
    created_at: datetime


class AttendanceOut(BaseModel):
    id: uuid.UUID
    person: Ref
    work_date: date
    check_in_at: datetime
    check_out_at: datetime | None
    note: str | None


class TaskBrief(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    priority: str
    project: Ref
    due_date: date | None
    is_overdue: bool


class MyWork(BaseModel):
    open_tasks: list[TaskBrief]
    awaiting_my_review: list[TaskBrief]
    leave_requests: list[LeaveOut]
    leave_to_approve: list[LeaveOut]
    attendance_today: AttendanceOut | None
    unread_notifications: int


async def _today(db: AsyncSession, company_id: uuid.UUID) -> date:
    company = await db.get(Company, company_id)
    return datetime.now(ZoneInfo(company.timezone if company else "UTC")).date()


async def _leave_out(db: AsyncSession, rows: list[LeaveRequest]) -> list[LeaveOut]:
    ids = {r.user_id for r in rows} | {r.decided_by_user_id for r in rows if r.decided_by_user_id}
    names = (
        {u.id: u.full_name for u in await db.scalars(select(User).where(User.id.in_(ids)))}
        if ids
        else {}
    )
    return [
        LeaveOut(
            id=r.id,
            person=Ref(id=r.user_id, name=names.get(r.user_id, "")),
            type=r.type,
            start_date=r.start_date,
            end_date=r.end_date,
            days=(r.end_date - r.start_date).days + 1,
            reason=r.reason,
            status=r.status,
            decided_by=Ref(id=r.decided_by_user_id, name=names.get(r.decided_by_user_id, ""))
            if r.decided_by_user_id
            else None,
            decided_at=r.decided_at,
            decision_note=r.decision_note,
            created_at=r.created_at,
        )
        for r in rows
    ]


def _attendance_out(record: AttendanceRecord, name: str) -> AttendanceOut:
    return AttendanceOut(
        id=record.id,
        person=Ref(id=record.user_id, name=name),
        work_date=record.work_date,
        check_in_at=record.check_in_at,
        check_out_at=record.check_out_at,
        note=record.note,
    )


async def _can_decide(db: AsyncSession, auth: AuthContext, leave: LeaveRequest) -> bool:
    if leave.user_id == auth.user.id:
        return False
    profile = await db.get(EmployeeProfile, leave.user_id)
    if profile and profile.manager_user_id == auth.user.id:
        return True
    context = employee_context(
        auth.user.company_id, leave.user_id, profile.department_id if profile else None
    )
    return is_allowed(auth.principal, "employee.approve", context)


async def _approvable(db: AsyncSession, auth: AuthContext) -> list[LeaveRequest]:
    pending = list(
        await db.scalars(
            select(LeaveRequest)
            .where(
                LeaveRequest.company_id == auth.user.company_id,
                LeaveRequest.status == "pending",
                LeaveRequest.user_id != auth.user.id,
            )
            .order_by(LeaveRequest.start_date)
        )
    )
    return [r for r in pending if await _can_decide(db, auth, r)]


def _brief(task: Task, project: Project, today: date) -> TaskBrief:
    return TaskBrief(
        id=task.id,
        title=task.title,
        status=task.status,
        priority=task.priority,
        project=Ref(id=project.id, name=project.name),
        due_date=task.due_date,
        is_overdue=bool(
            task.due_date and task.due_date < today and task.status in work_service.OPEN_STATUSES
        ),
    )


@router.get("/me/work", response_model=MyWork)
async def my_work(
    auth: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)
) -> MyWork:
    today = await _today(db, auth.user.company_id)
    open_rows = (
        await db.execute(
            select(Task, Project)
            .join(Project, Project.id == Task.project_id)
            .where(
                Task.assignee_user_id == auth.user.id, Task.status.in_(work_service.OPEN_STATUSES)
            )
            .order_by(Task.due_date.nulls_last(), work_service.PRIORITY_ORDER)
            .limit(30)
        )
    ).all()
    review_rows = (
        await db.execute(
            select(Task, Project)
            .join(Project, Project.id == Task.project_id)
            .where(
                Task.company_id == auth.user.company_id,
                Task.status.in_((TaskStatus.SUBMITTED, TaskStatus.UNDER_REVIEW)),
                or_(Task.assignee_user_id.is_(None), Task.assignee_user_id != auth.user.id),
            )
            .limit(100)
        )
    ).all()
    awaiting = [
        (t, p)
        for t, p in review_rows
        if is_allowed(auth.principal, "task.approve", work_service.task_context(t, p))
    ][:30]
    mine = list(
        await db.scalars(
            select(LeaveRequest)
            .where(LeaveRequest.user_id == auth.user.id)
            .order_by(LeaveRequest.start_date.desc())
            .limit(10)
        )
    )
    attendance = await db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.user_id == auth.user.id, AttendanceRecord.work_date == today
        )
    )
    _, _, unread = await list_notifications(db, auth.user.id, unread_only=True, limit=1, offset=0)
    return MyWork(
        open_tasks=[_brief(t, p, today) for t, p in open_rows],
        awaiting_my_review=[_brief(t, p, today) for t, p in awaiting],
        leave_requests=await _leave_out(db, mine),
        leave_to_approve=await _leave_out(db, await _approvable(db, auth)),
        attendance_today=_attendance_out(attendance, auth.user.full_name) if attendance else None,
        unread_notifications=unread,
    )


@router.post("/leave-requests", response_model=LeaveOut, status_code=201)
async def request_leave(
    payload: LeaveIn,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> LeaveOut:
    overlap = await db.scalar(
        select(LeaveRequest.id).where(
            LeaveRequest.user_id == auth.user.id,
            LeaveRequest.status.in_(("pending", "approved")),
            LeaveRequest.start_date <= payload.end_date,
            LeaveRequest.end_date >= payload.start_date,
        )
    )
    if overlap:
        raise ConflictError(
            "You already have leave requested for some of these dates.", code="leave_overlap"
        )
    leave = LeaveRequest(
        company_id=auth.user.company_id, user_id=auth.user.id, **payload.model_dump()
    )
    db.add(leave)
    await db.flush()
    profile = await db.get(EmployeeProfile, auth.user.id)
    await notify(
        db,
        company_id=auth.user.company_id,
        user_ids=[profile.manager_user_id if profile else None],
        kind="leave.requested",
        title=f"{auth.user.full_name} requested {payload.type} leave",
        body=f"{payload.start_date} to {payload.end_date}",
        link="/app/me",
        exclude=auth.user.id,
    )
    await record_event(
        db,
        action="leave.request",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=auth.user.id,
        company_id=auth.user.company_id,
        resource_type="leave_request",
        resource_id=leave.id,
        meta=meta,
    )
    await db.commit()
    await db.refresh(leave)
    return (await _leave_out(db, [leave]))[0]


@router.post("/leave-requests/{leave_id}/decision", response_model=LeaveOut)
async def decide_leave(
    leave_id: uuid.UUID,
    payload: LeaveDecision,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> LeaveOut:
    leave = await db.scalar(
        select(LeaveRequest).where(
            LeaveRequest.id == leave_id, LeaveRequest.company_id == auth.user.company_id
        )
    )
    if leave is None:
        raise NotFoundError("Leave request not found.")
    if not await _can_decide(db, auth, leave):
        raise PermissionDeniedError("Only the person's manager or HR can decide this request.")
    if leave.status != "pending":
        raise AppError("This request has already been decided.", code="already_decided")
    leave.status = payload.decision
    leave.decided_by_user_id = auth.user.id
    leave.decided_at = utc_now()
    leave.decision_note = payload.note.strip() or None
    await notify(
        db,
        company_id=auth.user.company_id,
        user_ids=[leave.user_id],
        kind=f"leave.{payload.decision}",
        title=f"Your leave request was {payload.decision}",
        body=payload.note,
        link="/app/me",
    )
    await record_event(
        db,
        action="leave.decide",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=auth.user.id,
        company_id=auth.user.company_id,
        resource_type="leave_request",
        resource_id=leave.id,
        meta=meta,
        details={"decision": payload.decision},
    )
    await db.commit()
    await db.refresh(leave)
    return (await _leave_out(db, [leave]))[0]


@router.post("/leave-requests/{leave_id}/cancel", response_model=LeaveOut)
async def cancel_leave(
    leave_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> LeaveOut:
    leave = await db.scalar(
        select(LeaveRequest).where(
            LeaveRequest.id == leave_id, LeaveRequest.user_id == auth.user.id
        )
    )
    if leave is None:
        raise NotFoundError("Leave request not found.")
    if leave.status not in ("pending", "approved") or leave.start_date <= date.today():
        raise AppError(
            "Only future pending or approved leave can be cancelled.", code="cannot_cancel"
        )
    leave.status = "cancelled"
    await db.commit()
    await db.refresh(leave)
    return (await _leave_out(db, [leave]))[0]


class CheckIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


@router.post("/attendance/check-in", response_model=AttendanceOut, status_code=201)
async def check_in(
    payload: CheckIn,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> AttendanceOut:
    today = await _today(db, auth.user.company_id)
    if await db.scalar(
        select(AttendanceRecord.id).where(
            AttendanceRecord.user_id == auth.user.id, AttendanceRecord.work_date == today
        )
    ):
        raise ConflictError("You have already checked in today.", code="already_checked_in")
    record = AttendanceRecord(
        company_id=auth.user.company_id,
        user_id=auth.user.id,
        work_date=today,
        check_in_at=utc_now(),
        note=payload.note,
    )
    db.add(record)
    await db.commit()
    return _attendance_out(record, auth.user.full_name)


@router.post("/attendance/check-out", response_model=AttendanceOut)
async def check_out(
    auth: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)
) -> AttendanceOut:
    today = await _today(db, auth.user.company_id)
    record = await db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.user_id == auth.user.id, AttendanceRecord.work_date == today
        )
    )
    if record is None:
        raise AppError("Check in first.", code="not_checked_in")
    if record.check_out_at:
        raise ConflictError("You have already checked out today.", code="already_checked_out")
    record.check_out_at = utc_now()
    await db.commit()
    return _attendance_out(record, auth.user.full_name)


@router.get("/attendance", response_model=list[AttendanceOut])
async def attendance(
    team: bool = False,
    days: int = Query(14, ge=1, le=90),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[AttendanceOut]:
    since = await _today(db, auth.user.company_id) - timedelta(days=days - 1)
    query = (
        select(AttendanceRecord, User)
        .join(User, User.id == AttendanceRecord.user_id)
        .where(
            AttendanceRecord.company_id == auth.user.company_id, AttendanceRecord.work_date >= since
        )
    )
    if team:
        if not is_allowed(auth.principal, "employee.read"):
            raise PermissionDeniedError("Viewing team attendance requires employee access.")
        query = query.where(department_member_condition(auth.principal, "employee.read"))
    else:
        query = query.where(AttendanceRecord.user_id == auth.user.id)
    rows = await db.execute(query.order_by(AttendanceRecord.work_date.desc(), User.full_name))
    return [_attendance_out(r, u.full_name) for r, u in rows]
