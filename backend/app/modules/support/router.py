import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.api.exports import csv_response, record_export
from app.api.pagination import Page, PageParams, page_params
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.support import service
from app.modules.support.service import (
    MessageIn,
    TicketDetail,
    TicketIn,
    TicketPatch,
    TicketSummary,
    TransitionIn,
)

router = APIRouter(prefix="/support", tags=["support"])


@router.get("/tickets", response_model=Page[TicketSummary])
async def list_tickets(
    q: str | None = Query(None, max_length=100),
    ticket_status: str | None = Query(None, alias="status", max_length=20),
    priority: str | None = Query(None, max_length=10),
    product_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    assignee: Literal["me", "unassigned"] | None = None,
    open_only: bool = False,
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("ticket.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[TicketSummary]:
    rows, total = await service.list_tickets(
        db,
        auth.principal,
        q=q,
        status=ticket_status,
        priority=priority,
        product_id=product_id,
        customer_id=customer_id,
        assignee=assignee,
        open_only=open_only,
        limit=page.limit,
        offset=page.offset,
    )
    items = await service.summaries(db, rows)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("/tickets", response_model=TicketDetail, status_code=201)
async def create_ticket(
    payload: TicketIn,
    auth: AuthContext = Depends(require_permission("ticket.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TicketDetail:
    t = await service.create_ticket(db, auth.user, auth.principal, payload, meta)
    return await service.detail(db, auth.principal, t)


@router.get("/tickets/export.csv")
async def export_tickets(
    auth: AuthContext = Depends(require_permission("ticket.export")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    rows, _ = await service.list_tickets(db, auth.principal, limit=10_000, offset=0)
    items = await service.summaries(db, rows)
    await record_export(db, auth, "tickets", len(items), meta)
    return csv_response(
        "tickets.csv",
        [
            "Reference",
            "Subject",
            "Status",
            "Priority",
            "Category",
            "Channel",
            "Product",
            "Customer",
            "Requester email",
            "Assignee",
            "Created",
            "First response",
            "Resolved",
        ],
        [
            [
                t.reference,
                t.subject,
                t.status,
                t.priority,
                t.category,
                t.channel,
                t.product.name if t.product else "",
                t.customer.name if t.customer else "",
                t.requester_email,
                t.assignee.name if t.assignee else "",
                t.created_at,
                t.first_response_at,
                t.resolved_at,
            ]
            for t in items
        ],
    )


@router.get("/metrics")
async def ticket_metrics(
    days: int = Query(30, ge=1, le=365),
    product_id: uuid.UUID | None = None,
    auth: AuthContext = Depends(require_permission("ticket.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await service.metrics(db, auth.principal, days=days, product_id=product_id)


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("ticket.read")),
    db: AsyncSession = Depends(get_db),
) -> TicketDetail:
    t = await service.get_ticket(db, auth.principal, ticket_id)
    return await service.detail(db, auth.principal, t)


@router.patch("/tickets/{ticket_id}", response_model=TicketDetail)
async def update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketPatch,
    auth: AuthContext = Depends(require_permission("ticket.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TicketDetail:
    t = await service.update_ticket(db, auth.user, auth.principal, ticket_id, payload, meta)
    return await service.detail(db, auth.principal, t)


@router.post("/tickets/{ticket_id}/transition", response_model=TicketDetail)
async def transition_ticket(
    ticket_id: uuid.UUID,
    payload: TransitionIn,
    auth: AuthContext = Depends(require_permission("ticket.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TicketDetail:
    t = await service.transition(db, auth.user, auth.principal, ticket_id, payload, meta)
    return await service.detail(db, auth.principal, t)


@router.post("/tickets/{ticket_id}/messages", response_model=TicketDetail, status_code=201)
async def add_message(
    ticket_id: uuid.UUID,
    payload: MessageIn,
    auth: AuthContext = Depends(require_permission("ticket.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TicketDetail:
    t = await service.add_message(db, auth.user, auth.principal, ticket_id, payload, meta)
    return await service.detail(db, auth.principal, t)
