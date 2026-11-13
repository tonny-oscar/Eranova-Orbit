"""Support tickets: lifecycle, communication history and service metrics."""

import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import ColumnElement, extract, false, func, or_, select, true

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.db.base import utc_now
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed, scope_filter
from app.modules.crm.models import Customer
from app.modules.crm.service import lookup
from app.modules.identity.models import User, UserStatus
from app.modules.notifications.service import notify
from app.modules.products.models import Product
from app.modules.products.service import escape_like
from app.modules.support.models import (
    TICKET_CATEGORIES,
    TICKET_CHANNELS,
    TICKET_PRIORITIES,
    TICKET_STATUSES,
    SupportTicket,
    TicketEvent,
    TicketMessage,
)

Status = Literal[TICKET_STATUSES]  # type: ignore[valid-type]
Priority = Literal[TICKET_PRIORITIES]  # type: ignore[valid-type]
Category = Literal[TICKET_CATEGORIES]  # type: ignore[valid-type]
Channel = Literal[TICKET_CHANNELS]  # type: ignore[valid-type]

OPEN_STATUSES = ("new", "open", "assigned", "in_progress", "waiting_customer")
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "new": ("open", "assigned", "in_progress", "waiting_customer", "resolved", "closed"),
    "open": ("assigned", "in_progress", "waiting_customer", "resolved", "closed"),
    "assigned": ("open", "in_progress", "waiting_customer", "resolved"),
    "in_progress": ("assigned", "waiting_customer", "resolved"),
    "waiting_customer": ("in_progress", "resolved", "closed"),
    "resolved": ("closed", "open"),
    "closed": ("open",),
}


# --- Schemas ---------------------------------------------------------------------------


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class TicketIn(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=20_000)
    product_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    requester_name: str | None = Field(default=None, max_length=200)
    requester_email: EmailStr | None = None
    category: Category = "question"
    priority: Priority = "medium"
    channel: Channel = "email"
    assignee_user_id: uuid.UUID | None = None


class TicketPatch(BaseModel):
    subject: str | None = Field(default=None, min_length=3, max_length=200)
    category: Category | None = None
    priority: Priority | None = None
    product_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    assignee_user_id: uuid.UUID | None = None


class TransitionIn(BaseModel):
    status: Status
    resolution: str | None = Field(default=None, max_length=10_000)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)
    internal: bool = False
    from_customer: bool = False


class MessageOut(BaseModel):
    id: uuid.UUID
    body: str
    internal: bool
    from_customer: bool
    author: Ref | None
    created_at: datetime


class EventOut(BaseModel):
    id: uuid.UUID
    kind: str
    from_value: str | None
    to_value: str | None
    actor: Ref | None
    created_at: datetime


class TicketSummary(BaseModel):
    id: uuid.UUID
    number: int
    reference: str
    subject: str
    status: str
    priority: str
    category: str
    channel: str
    product: Ref | None
    customer: Ref | None
    requester_name: str | None
    requester_email: str | None
    assignee: Ref | None
    first_response_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketSummary):
    description: str
    resolution: str | None
    closed_at: datetime | None
    messages: list[MessageOut]
    events: list[EventOut]
    allowed_statuses: list[str]
    can_update: bool


def reference(number: int) -> str:
    return f"T-{number}"


# --- Access ------------------------------------------------------------------------------


def ticket_context(t: SupportTicket) -> ResourceContext:
    return ResourceContext(
        company_id=t.company_id,
        product_ids=frozenset({t.product_id}) if t.product_id else frozenset(),
        owner_user_id=t.assignee_user_id,
    )


def ticket_scope(principal: Principal, permission: str = "ticket.read") -> ColumnElement[bool]:
    scope = scope_filter(principal, permission)
    if scope.company_wide:
        return true()
    conditions: list[ColumnElement[bool]] = []
    if scope.product_ids:
        conditions.append(SupportTicket.product_id.in_(scope.product_ids))
    if scope.own:
        conditions.append(SupportTicket.assignee_user_id == principal.user_id)
    return or_(*conditions) if conditions else false()


async def get_ticket(session, principal, ticket_id, permission="ticket.read") -> SupportTicket:
    t = await session.scalar(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id, SupportTicket.company_id == principal.company_id
        )
    )
    if t is None or not is_allowed(principal, "ticket.read", ticket_context(t)):
        raise NotFoundError("Ticket not found.")
    if permission != "ticket.read" and not is_allowed(principal, permission, ticket_context(t)):
        raise PermissionDeniedError("You cannot change this ticket.")
    return t


async def _check_refs(session, company_id, *, product_id=None, customer_id=None, assignee=None):
    if product_id and not await session.scalar(
        select(Product.id).where(Product.id == product_id, Product.company_id == company_id)
    ):
        raise AppError("Product not found.", code="invalid_product")
    if customer_id and not await session.scalar(
        select(Customer.id).where(Customer.id == customer_id, Customer.company_id == company_id)
    ):
        raise AppError("Customer not found.", code="invalid_customer")
    if assignee:
        user = await session.scalar(
            select(User).where(User.id == assignee, User.company_id == company_id)
        )
        if user is None or user.status != UserStatus.ACTIVE:
            raise AppError("The assignee must be an active user.", code="invalid_user")


async def _audit(session, actor, action, ticket_id, meta, details=None):
    await record_event(
        session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="ticket",
        resource_id=ticket_id,
        meta=meta,
        details=details or {},
    )


def _event(session, ticket, actor, kind, before=None, after=None):
    session.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_user_id=actor.id if actor else None,
            kind=kind,
            from_value=str(before)[:200] if before is not None else None,
            to_value=str(after)[:200] if after is not None else None,
        )
    )


# --- Queries ----------------------------------------------------------------------------


async def list_tickets(
    session,
    principal,
    *,
    q=None,
    status=None,
    priority=None,
    product_id=None,
    customer_id=None,
    assignee=None,
    open_only=False,
    limit=25,
    offset=0,
):
    conditions = [SupportTicket.company_id == principal.company_id, ticket_scope(principal)]
    if status:
        conditions.append(SupportTicket.status == status)
    if open_only:
        conditions.append(SupportTicket.status.in_(OPEN_STATUSES))
    if priority:
        conditions.append(SupportTicket.priority == priority)
    if product_id:
        conditions.append(SupportTicket.product_id == product_id)
    if customer_id:
        conditions.append(SupportTicket.customer_id == customer_id)
    if assignee == "me":
        conditions.append(SupportTicket.assignee_user_id == principal.user_id)
    elif assignee == "unassigned":
        conditions.append(SupportTicket.assignee_user_id.is_(None))
    if q and q.strip():
        text = q.strip()
        number = text.upper().removeprefix("T-")
        pattern = f"%{escape_like(text.lower())}%"
        options = [
            func.lower(SupportTicket.subject).like(pattern, escape="\\"),
            func.lower(func.coalesce(SupportTicket.requester_email, "")).like(pattern, escape="\\"),
        ]
        if number.isdigit():
            options.append(SupportTicket.number == int(number))
        conditions.append(or_(*options))
    total = await session.scalar(select(func.count()).select_from(SupportTicket).where(*conditions))
    rows = await session.scalars(
        select(SupportTicket)
        .where(*conditions)
        .order_by(SupportTicket.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def summaries(session, tickets: list[SupportTicket]) -> list[TicketSummary]:
    products = await lookup(session, Product, {t.product_id for t in tickets})
    customers = await lookup(session, Customer, {t.customer_id for t in tickets})
    users = await lookup(session, User, {t.assignee_user_id for t in tickets})
    out = []
    for t in tickets:
        product, customer, user = (
            products.get(t.product_id),
            customers.get(t.customer_id),
            users.get(t.assignee_user_id),
        )
        out.append(
            TicketSummary(
                id=t.id,
                number=t.number,
                reference=reference(t.number),
                subject=t.subject,
                status=t.status,
                priority=t.priority,
                category=t.category,
                channel=t.channel,
                product=Ref(id=product.id, name=product.name) if product else None,
                customer=Ref(id=customer.id, name=customer.name) if customer else None,
                requester_name=t.requester_name,
                requester_email=t.requester_email,
                assignee=Ref(id=user.id, name=user.full_name) if user else None,
                first_response_at=t.first_response_at,
                resolved_at=t.resolved_at,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )
    return out


async def detail(session, principal, t: SupportTicket) -> TicketDetail:
    summary = (await summaries(session, [t]))[0]
    messages = list(
        await session.scalars(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == t.id)
            .order_by(TicketMessage.created_at)
        )
    )
    events = list(
        await session.scalars(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == t.id)
            .order_by(TicketEvent.created_at)
        )
    )
    users = await lookup(
        session, User, {m.author_user_id for m in messages} | {e.actor_user_id for e in events}
    )

    def ref(user_id):
        u = users.get(user_id)
        return Ref(id=u.id, name=u.full_name) if u else None

    can_update = is_allowed(principal, "ticket.update", ticket_context(t))
    return TicketDetail(
        **summary.model_dump(),
        description=t.description,
        resolution=t.resolution,
        closed_at=t.closed_at,
        messages=[
            MessageOut(
                id=m.id,
                body=m.body,
                internal=m.internal,
                from_customer=m.from_customer,
                author=ref(m.author_user_id),
                created_at=m.created_at,
            )
            for m in messages
        ],
        events=[
            EventOut(
                id=e.id,
                kind=e.kind,
                from_value=e.from_value,
                to_value=e.to_value,
                actor=ref(e.actor_user_id),
                created_at=e.created_at,
            )
            for e in events
        ],
        allowed_statuses=list(TRANSITIONS[t.status]) if can_update else [],
        can_update=can_update,
    )


# --- Commands -----------------------------------------------------------------------------


async def create_ticket(session, actor, principal, payload: TicketIn, meta) -> SupportTicket:
    context = ResourceContext(
        company_id=actor.company_id,
        product_ids=frozenset({payload.product_id}) if payload.product_id else frozenset(),
        owner_user_id=payload.assignee_user_id or actor.id,
    )
    if not is_allowed(principal, "ticket.create", context):
        raise PermissionDeniedError("You cannot create tickets for this product.")
    await _check_refs(
        session,
        actor.company_id,
        product_id=payload.product_id,
        customer_id=payload.customer_id,
        assignee=payload.assignee_user_id,
    )
    ticket = SupportTicket(
        company_id=actor.company_id,
        created_by_user_id=actor.id,
        status="assigned" if payload.assignee_user_id else "new",
        **payload.model_dump(),
    )
    ticket.subject = ticket.subject.strip()
    session.add(ticket)
    await session.flush()
    await session.refresh(ticket, ["number"])
    _event(session, ticket, actor, "created", None, ticket.status)
    await _audit(session, actor, "ticket.create", ticket.id, meta, {"number": ticket.number})
    if ticket.assignee_user_id:
        await _notify_assignee(session, ticket, actor)
    await session.commit()
    return ticket


async def _notify_assignee(session, ticket, actor):
    await notify(
        session,
        company_id=ticket.company_id,
        user_ids=[ticket.assignee_user_id],
        kind="ticket.assigned",
        title=f"{reference(ticket.number)} assigned to you: {ticket.subject}",
        link=f"/app/support/{ticket.id}",
        exclude=actor.id,
    )


async def update_ticket(session, actor, principal, ticket_id, payload: TicketPatch, meta):
    t = await get_ticket(session, principal, ticket_id, "ticket.update")
    changes = payload.model_dump(exclude_unset=True)
    for field in ("subject", "category", "priority"):
        if field in changes and not changes[field]:
            raise AppError(f"{field.title()} cannot be empty.", code="invalid_field")
    await _check_refs(
        session,
        actor.company_id,
        product_id=changes.get("product_id"),
        customer_id=changes.get("customer_id"),
        assignee=changes.get("assignee_user_id"),
    )
    for field, value in changes.items():
        before = getattr(t, field)
        if before == value:
            continue
        setattr(t, field, value)
        if field in ("priority", "category"):
            _event(session, t, actor, field, before, value)
        if field == "assignee_user_id":
            _event(session, t, actor, "assignee", before, value)
            if value and t.status in ("new", "open"):
                _event(session, t, actor, "status", t.status, "assigned")
                t.status = "assigned"
            if value:
                await _notify_assignee(session, t, actor)
    await _audit(session, actor, "ticket.update", t.id, meta, {"fields": sorted(changes)})
    await session.commit()
    await session.refresh(t)
    return t


async def transition(session, actor, principal, ticket_id, payload: TransitionIn, meta):
    t = await get_ticket(session, principal, ticket_id, "ticket.update")
    if payload.status not in TRANSITIONS[t.status]:
        raise AppError(
            f"A ticket cannot move from {t.status.replace('_', ' ')} to "
            f"{payload.status.replace('_', ' ')}.",
            code="invalid_transition",
        )
    if payload.status == "assigned" and not t.assignee_user_id:
        raise AppError("Choose an assignee first.", code="assignee_required")
    now = utc_now()
    if payload.status in ("resolved", "closed"):
        resolution = (payload.resolution or t.resolution or "").strip()
        if not resolution:
            raise AppError("Record how the ticket was resolved.", code="resolution_required")
        t.resolution = resolution
        if payload.status == "resolved" or t.resolved_at is None:
            t.resolved_at = now
        if payload.status == "closed":
            t.closed_at = now
    if payload.status == "open":
        # Reopened: the next resolution is measured afresh.
        t.resolved_at = t.closed_at = None
    _event(session, t, actor, "status", t.status, payload.status)
    previous, t.status = t.status, payload.status
    await _audit(session, actor, "ticket.status", t.id, meta, {"from": previous, "to": t.status})
    await session.commit()
    await session.refresh(t)
    return t


async def add_message(session, actor, principal, ticket_id, payload: MessageIn, meta):
    t = await get_ticket(session, principal, ticket_id, "ticket.update")
    if payload.internal and payload.from_customer:
        raise AppError("A customer message cannot be an internal note.", code="invalid_message")
    session.add(
        TicketMessage(
            ticket_id=t.id,
            author_user_id=actor.id,
            body=payload.body.strip(),
            internal=payload.internal,
            from_customer=payload.from_customer,
        )
    )
    now = utc_now()
    if not payload.internal and not payload.from_customer:
        if t.first_response_at is None:
            t.first_response_at = now
        if t.status == "new":
            _event(session, t, actor, "status", t.status, "open")
            t.status = "open"
    if payload.from_customer and t.status in ("waiting_customer", "resolved"):
        _event(
            session,
            t,
            actor,
            "status",
            t.status,
            "in_progress" if t.status == "waiting_customer" else "open",
        )
        t.status = "in_progress" if t.status == "waiting_customer" else "open"
        if t.status == "open":
            t.resolved_at = None
    t.updated_at = now
    kind = (
        "note" if payload.internal else ("customer_message" if payload.from_customer else "reply")
    )
    await _audit(session, actor, f"ticket.{kind}", t.id, meta)
    if t.assignee_user_id and t.assignee_user_id != actor.id:
        await notify(
            session,
            company_id=t.company_id,
            user_ids=[t.assignee_user_id],
            kind="ticket.message",
            title=f"New {'note' if payload.internal else 'message'} on {reference(t.number)}",
            link=f"/app/support/{t.id}",
        )
    await session.commit()
    await session.refresh(t)
    return t


# --- Metrics ---------------------------------------------------------------------------------


async def metrics(session, principal, *, days: int = 30, product_id=None) -> dict:
    since = utc_now() - timedelta(days=days)
    base = [SupportTicket.company_id == principal.company_id, ticket_scope(principal)]
    if product_id:
        base.append(SupportTicket.product_id == product_id)

    by_status = dict(
        (
            await session.execute(
                select(SupportTicket.status, func.count())
                .where(*base)
                .group_by(SupportTicket.status)
            )
        ).all()
    )
    open_by_priority = dict(
        (
            await session.execute(
                select(SupportTicket.priority, func.count())
                .where(*base, SupportTicket.status.in_(OPEN_STATUSES))
                .group_by(SupportTicket.priority)
            )
        ).all()
    )
    created = await session.scalar(
        select(func.count())
        .select_from(SupportTicket)
        .where(*base, SupportTicket.created_at >= since)
    )
    resolved = await session.scalar(
        select(func.count())
        .select_from(SupportTicket)
        .where(*base, SupportTicket.resolved_at >= since)
    )

    def median_hours(end_col):
        hours = extract("epoch", end_col - SupportTicket.created_at) / 3600
        return select(func.percentile_cont(0.5).within_group(hours)).where(
            *base, SupportTicket.created_at >= since, end_col.is_not(None)
        )

    first_response = await session.scalar(median_hours(SupportTicket.first_response_at))
    resolution = await session.scalar(median_hours(SupportTicket.resolved_at))
    by_category = dict(
        (
            await session.execute(
                select(SupportTicket.category, func.count())
                .where(*base, SupportTicket.created_at >= since)
                .group_by(SupportTicket.category)
            )
        ).all()
    )
    return {
        "window_days": days,
        "generated_at": utc_now(),
        "open": sum(by_status.get(s, 0) for s in OPEN_STATUSES),
        "by_status": {s: by_status.get(s, 0) for s in TICKET_STATUSES},
        "open_by_priority": {p: open_by_priority.get(p, 0) for p in TICKET_PRIORITIES},
        "created": created or 0,
        "resolved": resolved or 0,
        "median_first_response_hours": round(first_response, 1)
        if first_response is not None
        else None,
        "median_resolution_hours": round(resolution, 1) if resolution is not None else None,
        "by_category": by_category,
    }
