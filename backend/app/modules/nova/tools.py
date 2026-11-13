"""NOVA's allowlisted tools.

Every tool has a typed argument schema, an authority level and the permission
it needs. Handlers call the same services as the UI, so record-level
authorization, validation and audit logging are identical. NOVA has no
generic database, SQL, shell or URL-fetch tool.
"""

import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.core.request_meta import RequestMeta
from app.modules.authorization.catalogue import ScopeType
from app.modules.authorization.models import Role
from app.modules.authorization.policy import Principal, scope_filter
from app.modules.crm import service as crm_service
from app.modules.crm.customers import ActivityIn
from app.modules.crm.customers import get_customer as crm_get_customer
from app.modules.crm.customers import scope_condition as customer_scope
from app.modules.crm.models import Customer, Lead
from app.modules.crm.schemas import LeadCreate, LeadUpdate
from app.modules.documents import service as document_service
from app.modules.documents.models import Document
from app.modules.identity.models import User, UserStatus
from app.modules.integrations.models import IntegrationConnection
from app.modules.integrations.service import scope_condition as integration_scope
from app.modules.marketing import service as marketing_service
from app.modules.marketing.models import CONTENT_KINDS, Campaign
from app.modules.people.models import Department
from app.modules.products.models import Product
from app.modules.products.service import escape_like, product_scope_condition
from app.modules.reports import generators
from app.modules.reports import service as report_service
from app.modules.support import service as support_service
from app.modules.support.models import SupportTicket
from app.modules.work import service as work_service
from app.modules.work.models import Project, Task
from app.modules.work.schemas import TaskIn

# "personal" tools only touch the user's own NOVA memory.
Authority = Literal["read", "personal", "execute", "approval"]


@dataclass
class ToolContext:
    session: AsyncSession
    user: User
    principal: Principal
    meta: RequestMeta
    settings: Settings


@dataclass
class ToolResult:
    summary: str
    data: Any = None
    links: list[dict[str, str]] = field(default_factory=list)


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    authority: Authority
    args: type[Args]
    handler: Callable[[ToolContext, Any], Awaitable[ToolResult]]
    permission: str | None = None
    approval_policy: Literal["self_confirm", "second_person"] | None = None
    approval_reason: str = ""
    describe: Callable[[Any], str] | None = None

    def available_to(self, principal: Principal) -> bool:
        return self.permission is None or not scope_filter(principal, self.permission).is_empty

    def schema(self) -> dict:
        params = self.args.model_json_schema()
        params.pop("title", None)
        for prop in params.get("properties", {}).values():
            prop.pop("title", None)
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": params},
        }


# --- Privacy helpers -------------------------------------------------------------------------


def mask_email(email: str | None, settings: Settings) -> str | None:
    if not email or settings.nova_share_contact_details:
        return email
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def _link(label: str, href: str) -> dict[str, str]:
    return {"label": label[:120], "href": href}


def _like(text: str) -> str:
    return f"%{escape_like(text.strip().lower())}%"


async def _find_product(ctx: ToolContext, ref: str) -> Product:
    cond = [
        Product.company_id == ctx.principal.company_id,
        product_scope_condition(scope_filter(ctx.principal, "product.read"), ctx.principal.user_id),
    ]
    try:
        cond.append(Product.id == uuid.UUID(ref))
    except ValueError:
        cond.append(or_(func.lower(Product.name) == ref.lower(), Product.slug == ref.lower()))
    product = await ctx.session.scalar(select(Product).where(*cond))
    if product is None:
        raise NotFoundError(f"No product you can access matches '{ref}'.")
    return product


async def _find_project(ctx: ToolContext, ref: str) -> Project:
    cond = [
        Project.company_id == ctx.principal.company_id,
        work_service.project_scope(ctx.principal, "project.read"),
    ]
    try:
        cond.append(Project.id == uuid.UUID(ref))
    except ValueError:
        cond.append(func.lower(Project.name) == ref.lower())
    project = await ctx.session.scalar(select(Project).where(*cond))
    if project is None:
        raise NotFoundError(f"No project you can access matches '{ref}'.")
    return project


async def _find_user(ctx: ToolContext, email: str) -> User:
    user = await ctx.session.scalar(
        select(User).where(
            User.company_id == ctx.principal.company_id,
            func.lower(User.email) == email.lower(),
            User.status == UserStatus.ACTIVE,
        )
    )
    if user is None:
        raise NotFoundError(f"No active colleague with email {email}.")
    return user


# --- Read tools ----------------------------------------------------------------------------------

RecordType = Literal[
    "product", "project", "task", "lead", "customer", "ticket", "campaign", "document"
]


class SearchArgs(Args):
    query: str = Field(
        min_length=2, max_length=100, description="Words to look for in names and titles"
    )
    types: list[RecordType] | None = Field(default=None, description="Limit to these record types")


async def search_records(ctx: ToolContext, a: SearchArgs) -> ToolResult:
    p, s, pattern = ctx.principal, ctx.session, _like(a.query)
    wanted = set(a.types or RecordType.__args__)
    found: list[dict] = []

    def can(permission: str) -> bool:
        return not scope_filter(p, permission).is_empty

    if "product" in wanted and can("product.read"):
        for r in await s.scalars(
            select(Product)
            .where(
                Product.company_id == p.company_id,
                product_scope_condition(scope_filter(p, "product.read"), p.user_id),
                func.lower(Product.name).like(pattern, escape="\\"),
            )
            .limit(5)
        ):
            found.append(
                {
                    "type": "product",
                    "id": str(r.id),
                    "name": r.name,
                    "status": r.lifecycle_status,
                    "href": f"/app/products/{r.id}",
                }
            )
    if "project" in wanted and can("project.read"):
        for r in await s.scalars(
            select(Project)
            .where(
                Project.company_id == p.company_id,
                work_service.project_scope(p, "project.read"),
                func.lower(Project.name).like(pattern, escape="\\"),
            )
            .limit(5)
        ):
            found.append(
                {
                    "type": "project",
                    "id": str(r.id),
                    "name": r.name,
                    "status": r.status,
                    "href": f"/app/projects/{r.id}",
                }
            )
    if "task" in wanted:
        for r in await s.scalars(
            select(Task)
            .where(
                Task.company_id == p.company_id,
                work_service.task_scope(p),
                func.lower(Task.title).like(pattern, escape="\\"),
            )
            .limit(8)
        ):
            found.append(
                {
                    "type": "task",
                    "id": str(r.id),
                    "name": r.title,
                    "status": r.status,
                    "due": r.due_date,
                    "href": f"/app/tasks/{r.id}",
                }
            )
    if "lead" in wanted and can("lead.read"):
        for r in await s.scalars(
            select(Lead)
            .where(
                Lead.company_id == p.company_id,
                crm_service._scope_condition(p),
                or_(
                    func.lower(Lead.full_name).like(pattern, escape="\\"),
                    func.lower(func.coalesce(Lead.organization, "")).like(pattern, escape="\\"),
                ),
            )
            .limit(5)
        ):
            found.append(
                {
                    "type": "lead",
                    "id": str(r.id),
                    "name": r.full_name,
                    "organization": r.organization,
                    "status": r.status,
                    "href": f"/app/leads/{r.id}",
                }
            )
    if "customer" in wanted and can("customer.read"):
        for r in await s.scalars(
            select(Customer)
            .where(
                Customer.company_id == p.company_id,
                customer_scope(p),
                func.lower(Customer.name).like(pattern, escape="\\"),
            )
            .limit(5)
        ):
            found.append(
                {
                    "type": "customer",
                    "id": str(r.id),
                    "name": r.name,
                    "status": r.status,
                    "href": f"/app/customers/{r.id}",
                }
            )
    if "ticket" in wanted and can("ticket.read"):
        for r in await s.scalars(
            select(SupportTicket)
            .where(
                SupportTicket.company_id == p.company_id,
                support_service.ticket_scope(p),
                func.lower(SupportTicket.subject).like(pattern, escape="\\"),
            )
            .limit(5)
        ):
            found.append(
                {
                    "type": "ticket",
                    "id": str(r.id),
                    "name": f"T-{r.number} {r.subject}",
                    "status": r.status,
                    "href": f"/app/support/{r.id}",
                }
            )
    if "campaign" in wanted and can("campaign.read"):
        for r in await s.scalars(
            select(Campaign)
            .where(
                Campaign.company_id == p.company_id,
                marketing_service.campaign_scope(p),
                func.lower(Campaign.name).like(pattern, escape="\\"),
            )
            .limit(5)
        ):
            found.append(
                {
                    "type": "campaign",
                    "id": str(r.id),
                    "name": r.name,
                    "status": r.status,
                    "href": f"/app/marketing/campaigns/{r.id}",
                }
            )
    if "document" in wanted and can("document.read"):
        for r in await s.scalars(
            select(Document)
            .where(
                Document.company_id == p.company_id,
                document_service.document_scope(p),
                func.lower(Document.title).like(pattern, escape="\\"),
            )
            .limit(5)
        ):
            found.append(
                {
                    "type": "document",
                    "id": str(r.id),
                    "name": r.title,
                    "category": r.category,
                    "href": f"/app/documents/{r.id}",
                }
            )
    return ToolResult(
        summary=f"Found {len(found)} matching record(s) for '{a.query}'.",
        data=found,
        links=[_link(f"{r['type']}: {r['name']}", r["href"]) for r in found[:10]],
    )


class NoArgs(Args):
    pass


async def my_work(ctx: ToolContext, _: NoArgs) -> ToolResult:
    today = date.today()
    rows = await ctx.session.execute(
        select(Task, Project)
        .join(Project, Project.id == Task.project_id)
        .where(Task.assignee_user_id == ctx.user.id, Task.status.in_(work_service.OPEN_STATUSES))
        .order_by(Task.due_date.nulls_last(), work_service.PRIORITY_ORDER)
        .limit(20)
    )
    tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "project": pr.name,
            "status": t.status,
            "priority": t.priority,
            "due": t.due_date,
            "overdue": bool(t.due_date and t.due_date < today),
            "href": f"/app/tasks/{t.id}",
        }
        for t, pr in rows
    ]
    follow_ups = []
    if not scope_filter(ctx.principal, "lead.read").is_empty:
        for lead in await ctx.session.scalars(
            select(Lead)
            .where(
                Lead.owner_user_id == ctx.user.id,
                Lead.next_follow_up <= today + timedelta(days=7),
                Lead.converted_customer_id.is_(None),
            )
            .order_by(Lead.next_follow_up)
            .limit(10)
        ):
            follow_ups.append(
                {
                    "id": str(lead.id),
                    "lead": lead.full_name,
                    "date": lead.next_follow_up,
                    "href": f"/app/leads/{lead.id}",
                }
            )
    overdue = sum(1 for t in tasks if t["overdue"])
    return ToolResult(
        summary=(
            f"{len(tasks)} open task(s), {overdue} overdue; "
            f"{len(follow_ups)} follow-up(s) due within a week."
        ),
        data={"tasks": tasks, "follow_ups": follow_ups},
        links=[_link(t["title"], t["href"]) for t in tasks[:8]],
    )


class ListTasksArgs(Args):
    scope: Literal["mine", "all"] = "mine"
    overdue_only: bool = False
    project: str | None = Field(default=None, max_length=150, description="Project name or id")
    limit: int = Field(default=15, ge=1, le=25)


async def list_tasks(ctx: ToolContext, a: ListTasksArgs) -> ToolResult:
    project = await _find_project(ctx, a.project) if a.project else None
    rows, total = await work_service.list_tasks(
        ctx.session,
        ctx.principal,
        project_id=project.id if project else None,
        assignee_id=ctx.user.id if a.scope == "mine" else None,
        status=None,
        open_only=True,
        overdue_only=a.overdue_only,
        q=None,
        top_level_only=False,
        limit=a.limit,
        offset=0,
    )
    users = await crm_service.lookup(ctx.session, User, {t.assignee_user_id for t, _ in rows})
    items = [
        {
            "id": str(t.id),
            "title": t.title,
            "project": pr.name,
            "status": t.status,
            "priority": t.priority,
            "due": t.due_date,
            "assignee": users[t.assignee_user_id].full_name
            if t.assignee_user_id in users
            else None,
            "href": f"/app/tasks/{t.id}",
        }
        for t, pr in rows
    ]
    return ToolResult(
        summary=f"{total} open task(s) match; showing {len(items)}.",
        data=items,
        links=[_link(i["title"], i["href"]) for i in items[:10]],
    )


class GetRecordArgs(Args):
    type: RecordType
    id: uuid.UUID


async def get_record(ctx: ToolContext, a: GetRecordArgs) -> ToolResult:
    s, p, st = ctx.session, ctx.principal, ctx.settings
    if a.type == "task":
        t, pr = await work_service.get_task(s, p, a.id)
        data = {
            "title": t.title,
            "description": t.description[:2000],
            "project": pr.name,
            "status": t.status,
            "priority": t.priority,
            "due": t.due_date,
            "completed_at": t.completed_at,
        }
        href = f"/app/tasks/{t.id}"
    elif a.type == "lead":
        lead = await crm_service.get_lead(s, p, a.id)
        data = {
            "name": lead.full_name,
            "organization": lead.organization,
            "email": mask_email(lead.email, st),
            "stage": lead.status,
            "priority": lead.priority,
            "source": lead.source,
            "next_follow_up": lead.next_follow_up,
            "notes": (lead.notes or "")[:2000],
        }
        href = f"/app/leads/{lead.id}"
    elif a.type == "customer":
        c = await crm_get_customer(s, p, a.id)
        data = {
            "name": c.name,
            "status": c.status,
            "industry": c.industry,
            "notes": (c.notes or "")[:2000],
        }
        href = f"/app/customers/{c.id}"
    elif a.type == "ticket":
        t = await support_service.get_ticket(s, p, a.id)
        data = {
            "reference": f"T-{t.number}",
            "subject": t.subject,
            "status": t.status,
            "priority": t.priority,
            "category": t.category,
            "description": t.description[:2000],
            "resolution": t.resolution,
        }
        href = f"/app/support/{t.id}"
    elif a.type == "project":
        pr = await work_service.get_project(s, p, a.id)
        data = {
            "name": pr.name,
            "status": pr.status,
            "priority": pr.priority,
            "due": pr.due_date,
            "description": pr.description[:2000],
        }
        href = f"/app/projects/{pr.id}"
    elif a.type == "product":
        prod = await _find_product(ctx, str(a.id))
        data = {
            "name": prod.name,
            "status": prod.lifecycle_status,
            "description": (prod.description or "")[:2000],
            "details_confirmed": prod.details_confirmed,
        }
        href = f"/app/products/{prod.id}"
    elif a.type == "campaign":
        c = await marketing_service.get_campaign(s, p, a.id)
        data = {
            "name": c.name,
            "status": c.status,
            "objective": c.objective[:2000],
            "start": c.start_date,
            "end": c.end_date,
            "channels": c.channels,
        }
        href = f"/app/marketing/campaigns/{c.id}"
    else:
        d = await document_service.get_document(s, p, a.id)
        data = {
            "title": d.title,
            "category": d.category,
            "description": d.description[:2000],
            "version": d.current_version,
            "note": "File contents are not read by NOVA.",
        }
        href = f"/app/documents/{d.id}"
    return ToolResult(summary=f"Loaded {a.type}.", data=data, links=[_link(f"Open {a.type}", href)])


class ListTicketsArgs(Args):
    open_only: bool = True
    priority: Literal["low", "medium", "high", "urgent"] | None = None
    limit: int = Field(default=15, ge=1, le=25)


async def list_tickets(ctx: ToolContext, a: ListTicketsArgs) -> ToolResult:
    rows, total = await support_service.list_tickets(
        ctx.session,
        ctx.principal,
        priority=a.priority,
        open_only=a.open_only,
        limit=a.limit,
        offset=0,
    )
    items = [
        {
            "id": str(t.id),
            "reference": f"T-{t.number}",
            "subject": t.subject,
            "status": t.status,
            "priority": t.priority,
            "created": t.created_at,
            "href": f"/app/support/{t.id}",
        }
        for t in rows
    ]
    return ToolResult(
        summary=f"{total} ticket(s) match; showing {len(items)}.",
        data=items,
        links=[_link(f"{i['reference']} {i['subject']}", i["href"]) for i in items[:10]],
    )


class TicketArgs(Args):
    ticket_id: uuid.UUID


async def ticket_history(ctx: ToolContext, a: TicketArgs) -> ToolResult:
    t = await support_service.get_ticket(ctx.session, ctx.principal, a.ticket_id)
    detail = await support_service.detail(ctx.session, ctx.principal, t)
    return ToolResult(
        summary=f"T-{t.number}: {len(detail.messages)} message(s), status {t.status}.",
        data={
            "subject": t.subject,
            "status": t.status,
            "description": t.description[:3000],
            "messages": [
                {
                    "from": "customer"
                    if m.from_customer
                    else ("internal note" if m.internal else "staff"),
                    "at": m.created_at,
                    "text": m.body[:2000],
                }
                for m in detail.messages[-30:]
            ],
        },
        links=[_link(f"T-{t.number} {t.subject}", f"/app/support/{t.id}")],
    )


class SummaryArgs(Args):
    days: int = Field(default=30, ge=1, le=366)


async def business_summary(ctx: ToolContext, a: SummaryArgs) -> ToolResult:
    end = date.today()
    period = generators.Period(end - timedelta(days=a.days - 1), end)
    report = await generators.generate(ctx.session, ctx.principal, "executive", period)
    return ToolResult(
        summary=(
            f"Executive summary for the last {a.days} days "
            f"({len(report['sections'])} areas you can see)."
        ),
        data=report["sections"],
        links=[_link("Executive report", "/app/reports/executive")],
    )


class ReportArgs(Args):
    key: Literal[
        "executive", "sales", "support", "delivery", "marketing", "traffic", "product", "people"
    ]
    start: date | None = None
    end: date | None = None


async def run_report(ctx: ToolContext, a: ReportArgs) -> ToolResult:
    period = report_service.resolve_period(a.start, a.end)
    report = await report_service.run_report(ctx.session, ctx.principal, a.key, period)
    return ToolResult(
        summary=f"{report['title']} report, {period.start} to {period.end}.",
        data=report["sections"],
        links=[_link(f"{report['title']} report", f"/app/reports/{a.key}")],
    )


class ProductArgs(Args):
    product: str = Field(min_length=1, max_length=150, description="Product name, slug or id")


async def product_status(ctx: ToolContext, a: ProductArgs) -> ToolResult:
    product = await _find_product(ctx, a.product)
    end = date.today()
    sections = await generators.product(
        ctx.session, ctx.principal, generators.Period(end - timedelta(days=29), end), product.id
    )
    integrations = []
    if not scope_filter(ctx.principal, "integration.read").is_empty:
        for c in await ctx.session.scalars(
            select(IntegrationConnection).where(
                IntegrationConnection.product_id == product.id, integration_scope(ctx.principal)
            )
        ):
            integrations.append(
                {
                    "name": c.name,
                    "provider": c.provider,
                    "status": c.status,
                    "last_success_at": c.last_success_at,
                    "last_error": c.last_error,
                }
            )
    return ToolResult(
        summary=f"{product.name} is {product.lifecycle_status}.",
        data={
            "product": product.name,
            "lifecycle_status": product.lifecycle_status,
            "details_confirmed": product.details_confirmed,
            "figures": sections[0].as_dict(),
            "integrations": integrations,
        },
        links=[_link(product.name, f"/app/products/{product.id}")],
    )


# --- Execute tools -------------------------------------------------------------------


class CreateTaskArgs(Args):
    project: str = Field(min_length=1, max_length=150, description="Project name or id")
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    assignee_email: EmailStr | None = None
    due_date: date | None = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"


async def create_task(ctx: ToolContext, a: CreateTaskArgs) -> ToolResult:
    project = await _find_project(ctx, a.project)
    assignee = await _find_user(ctx, a.assignee_email) if a.assignee_email else None
    task = await work_service.create_task(
        ctx.session,
        ctx.user,
        ctx.principal,
        TaskIn(
            project_id=project.id,
            title=a.title,
            description=a.description,
            priority=a.priority,
            assignee_user_id=assignee.id if assignee else None,
            due_date=a.due_date,
        ),
        ctx.meta,
    )
    return ToolResult(
        summary=f"Created task '{task.title}' in {project.name}"
        + (f", assigned to {assignee.full_name}" if assignee else "")
        + ".",
        data={"id": str(task.id), "status": task.status},
        links=[_link(task.title, f"/app/tasks/{task.id}")],
    )


class CreateLeadArgs(Args):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    organization: str | None = Field(default=None, max_length=200)
    product: str | None = Field(default=None, max_length=150, description="Product name or slug")
    notes: str = Field(default="", max_length=5000)
    next_follow_up: date | None = None


async def create_lead(ctx: ToolContext, a: CreateLeadArgs) -> ToolResult:
    product = await _find_product(ctx, a.product) if a.product else None
    lead = await crm_service.create_lead(
        ctx.session,
        actor=ctx.user,
        principal=ctx.principal,
        payload=LeadCreate(
            full_name=a.full_name,
            email=a.email,
            organization=a.organization,
            product_id=product.id if product else None,
            source="nova",
            notes=a.notes,
            next_follow_up=a.next_follow_up,
        ),
        meta=ctx.meta,
    )
    return ToolResult(
        summary=f"Created lead {lead.full_name}.",
        data={"id": str(lead.id)},
        links=[_link(lead.full_name, f"/app/leads/{lead.id}")],
    )


class FollowUpArgs(Args):
    lead_id: uuid.UUID
    date: date
    note: str = Field(default="", max_length=2000)


async def schedule_follow_up(ctx: ToolContext, a: FollowUpArgs) -> ToolResult:
    if a.date < date.today():
        raise AppError("Follow-ups must be today or later.", code="invalid_date")
    lead = await crm_service.update_lead(
        ctx.session,
        actor=ctx.user,
        principal=ctx.principal,
        lead_id=a.lead_id,
        payload=LeadUpdate(next_follow_up=a.date),
        meta=ctx.meta,
    )
    if a.note:
        await crm_service.add_lead_activity(
            ctx.session,
            actor=ctx.user,
            principal=ctx.principal,
            lead_id=lead.id,
            payload=ActivityIn(type="note", subject=f"Follow-up planned for {a.date}", body=a.note),
            meta=ctx.meta,
        )
    return ToolResult(
        summary=f"Follow-up with {lead.full_name} set for {a.date}.",
        links=[_link(lead.full_name, f"/app/leads/{lead.id}")],
    )


class DraftContentArgs(Args):
    title: str = Field(min_length=2, max_length=200)
    kind: Literal[CONTENT_KINDS]  # type: ignore[valid-type]
    body: str = Field(min_length=1, max_length=20_000)
    channel: str | None = Field(default=None, max_length=20)
    campaign_id: uuid.UUID | None = None


async def draft_content(ctx: ToolContext, a: DraftContentArgs) -> ToolResult:
    item = await marketing_service.create_content(
        ctx.session,
        ctx.user,
        ctx.principal,
        marketing_service.ContentIn(
            title=a.title, kind=a.kind, body=a.body, channel=a.channel, campaign_id=a.campaign_id
        ),
        ctx.meta,
    )
    return ToolResult(
        summary=(
            f"Saved draft '{item.title}'. It needs human review before it can be "
            "scheduled or published."
        ),
        data={"id": str(item.id), "status": item.status},
        links=[_link(item.title, f"/app/marketing/content/{item.id}")],
    )


class TicketNoteArgs(Args):
    ticket_id: uuid.UUID
    body: str = Field(
        min_length=1, max_length=10_000, description="Draft reply or summary for staff"
    )


async def add_ticket_note(ctx: ToolContext, a: TicketNoteArgs) -> ToolResult:
    t = await support_service.add_message(
        ctx.session,
        ctx.user,
        ctx.principal,
        a.ticket_id,
        support_service.MessageIn(body=f"[Drafted by NOVA, not sent]\n{a.body}", internal=True),
        ctx.meta,
    )
    return ToolResult(
        summary=f"Added an internal note to T-{t.number}. Nothing was sent to the customer.",
        links=[_link(f"T-{t.number}", f"/app/support/{t.id}")],
    )


# --- Approval-required tools ---------------------------------------------------------


class DeleteArgs(Args):
    id: uuid.UUID
    reason: str = Field(min_length=3, max_length=300)


async def delete_document(ctx: ToolContext, a: DeleteArgs) -> ToolResult:
    d = await document_service.get_document(ctx.session, ctx.principal, a.id)
    title = d.title
    await document_service.delete(ctx.session, ctx.user, ctx.principal, a.id, ctx.meta)
    return ToolResult(summary=f"Deleted document '{title}'.")


async def delete_campaign(ctx: ToolContext, a: DeleteArgs) -> ToolResult:
    c = await marketing_service.get_campaign(ctx.session, ctx.principal, a.id)
    name = c.name
    await marketing_service.delete_campaign(ctx.session, ctx.user, ctx.principal, a.id, ctx.meta)
    return ToolResult(summary=f"Deleted campaign '{name}'.")


class AssignRoleArgs(Args):
    user_email: EmailStr
    role: str = Field(
        min_length=2, max_length=60, pattern=r"^[a-z0-9_]+$", description="Role slug, e.g. sales"
    )
    scope_type: Literal["company", "department", "product", "project", "own"] = "company"
    scope: str | None = Field(
        default=None,
        max_length=150,
        description="Product, department or project name for scoped roles",
    )
    reason: str = Field(min_length=3, max_length=300)


async def assign_role(ctx: ToolContext, a: AssignRoleArgs) -> ToolResult:
    from app.modules.authorization import service as authz

    target = await _find_user(ctx, a.user_email)
    role = await ctx.session.scalar(
        select(Role).where(Role.company_id == ctx.user.company_id, Role.slug == a.role)
    )
    if role is None:
        raise NotFoundError(f"No role '{a.role}'.")
    scope_id = None
    if a.scope_type == "product":
        scope_id = (await _find_product(ctx, a.scope or "")).id
    elif a.scope_type == "project":
        scope_id = (await _find_project(ctx, a.scope or "")).id
    elif a.scope_type == "department":
        dept = await ctx.session.scalar(
            select(Department).where(
                Department.company_id == ctx.user.company_id,
                func.lower(Department.name) == (a.scope or "").lower(),
            )
        )
        if dept is None:
            raise NotFoundError(f"No department '{a.scope}'.")
        scope_id = dept.id
    await authz.assign_role(
        ctx.session,
        actor=ctx.user,
        principal=ctx.principal,
        target_user_id=target.id,
        role_id=role.id,
        scope_type=ScopeType(a.scope_type),
        scope_id=scope_id,
        meta=ctx.meta,
    )
    scope_label = f"{a.scope_type}: {a.scope}" if a.scope else a.scope_type
    return ToolResult(
        summary=f"Gave {target.full_name} the {role.name} role ({scope_label}).",
        links=[_link(target.full_name, f"/app/settings/users/{target.id}")],
    )


# --- Personal memory tools -----------------------------------------------------------


class RememberArgs(Args):
    content: str = Field(min_length=3, max_length=500, description="One short fact or preference")
    category: Literal["preference", "fact", "goal", "style"] = "fact"
    user_asked: bool = Field(
        default=False, description="True only if the user asked you to remember"
    )


async def remember(ctx: ToolContext, a: RememberArgs) -> ToolResult:
    from app.modules.nova import memory

    profile = await memory.get_profile(ctx.session, ctx.user)
    if not a.user_asked and not profile.learning_enabled:
        raise AppError("Learning is switched off for this user.", code="learning_disabled")
    note, created = await memory.add_memory(
        ctx.session, ctx.user, a.content, a.category, "told" if a.user_asked else "learned"
    )
    await ctx.session.commit()
    return ToolResult(
        summary=f"{'Remembered' if created else 'Already knew'}: {note.content}",
        data={"id": str(note.id)},
        links=[_link("What NOVA remembers", "/app/nova/memory")],
    )


class ForgetArgs(Args):
    text: str = Field(min_length=2, max_length=200, description="Words from the note to forget")


async def forget(ctx: ToolContext, a: ForgetArgs) -> ToolResult:
    from app.modules.nova import memory

    removed = await memory.forget_matching(ctx.session, ctx.user, a.text)
    await ctx.session.commit()
    if not removed:
        return ToolResult(summary=f"Nothing in memory matched '{a.text}'.")
    return ToolResult(
        summary=f"Forgot {len(removed)} note(s): " + "; ".join(_short(r, 60) for r in removed),
        links=[_link("What NOVA remembers", "/app/nova/memory")],
    )


async def what_you_know(ctx: ToolContext, _: NoArgs) -> ToolResult:
    from app.modules.nova import memory

    notes = [m for m in await memory.list_memories(ctx.session, ctx.user) if m.active]
    return ToolResult(
        summary=f"{len(notes)} note(s) in memory.",
        data=[
            {"content": m.content, "category": m.category, "source": m.source} for m in notes[:40]
        ],
        links=[_link("What NOVA remembers", "/app/nova/memory")],
    )


def _short(text: str, n: int = 80) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        Tool(
            "remember",
            "Save a short lasting fact, preference, goal or answer-style note about the user.",
            "personal",
            RememberArgs,
            remember,
        ),
        Tool(
            "forget",
            "Delete the user's memory notes that match some words.",
            "personal",
            ForgetArgs,
            forget,
        ),
        Tool(
            "what_you_know",
            "List what NOVA remembers about the user.",
            "read",
            NoArgs,
            what_you_know,
        ),
        Tool(
            "search_records",
            "Search products, projects, tasks, leads, customers, tickets, campaigns and "
            "documents the user can access by name or title.",
            "read",
            SearchArgs,
            search_records,
        ),
        Tool(
            "my_work",
            "The user's own open tasks (with overdue flags) and upcoming lead follow-ups.",
            "read",
            NoArgs,
            my_work,
        ),
        Tool(
            "list_tasks",
            "List open tasks, optionally only overdue, for the user or everyone they can "
            "see, optionally within one project.",
            "read",
            ListTasksArgs,
            list_tasks,
        ),
        Tool(
            "get_record",
            "Load one record by type and id (use ids from search results).",
            "read",
            GetRecordArgs,
            get_record,
        ),
        Tool(
            "list_tickets",
            "List support tickets, open ones by default.",
            "read",
            ListTicketsArgs,
            list_tickets,
            permission="ticket.read",
        ),
        Tool(
            "ticket_history",
            "Full conversation of one support ticket, for summarising or drafting a reply.",
            "read",
            TicketArgs,
            ticket_history,
            permission="ticket.read",
        ),
        Tool(
            "business_summary",
            "Headline figures across products, sales, delivery, support and marketing "
            "the user can see.",
            "read",
            SummaryArgs,
            business_summary,
        ),
        Tool(
            "run_report",
            "Generate a named report for a date range.",
            "read",
            ReportArgs,
            run_report,
            permission="report.read",
        ),
        Tool(
            "product_status",
            "Status, work, support and integration health of one product.",
            "read",
            ProductArgs,
            product_status,
            permission="product.read",
        ),
        Tool(
            "create_task",
            "Create a task in a project, optionally assigned and with a due date.",
            "execute",
            CreateTaskArgs,
            create_task,
            permission="task.create",
            describe=lambda a: (
                f"Create task '{_short(a.title)}' in {a.project}"
                + (f" for {a.assignee_email}" if a.assignee_email else "")
                + (f", due {a.due_date}" if a.due_date else "")
            ),
        ),
        Tool(
            "create_lead",
            "Create a CRM lead.",
            "execute",
            CreateLeadArgs,
            create_lead,
            permission="lead.create",
            describe=lambda a: (
                f"Create lead {a.full_name}" + (f" ({a.organization})" if a.organization else "")
            ),
        ),
        Tool(
            "schedule_follow_up",
            "Set the next follow-up date on a lead, with an optional note.",
            "execute",
            FollowUpArgs,
            schedule_follow_up,
            permission="lead.update",
            describe=lambda a: f"Set a follow-up on lead {a.lead_id} for {a.date}",
        ),
        Tool(
            "draft_content",
            "Save marketing content as a draft for human review (never publishes).",
            "execute",
            DraftContentArgs,
            draft_content,
            permission="campaign.create",
            describe=lambda a: f"Save draft '{_short(a.title)}'",
        ),
        Tool(
            "add_ticket_note",
            "Add an internal staff note (e.g. a drafted reply or summary) to a ticket. "
            "Never sent to the customer.",
            "execute",
            TicketNoteArgs,
            add_ticket_note,
            permission="ticket.update",
            describe=lambda a: f"Add an internal note to ticket {a.ticket_id}",
        ),
        Tool(
            "delete_document",
            "Request deletion of a document. Requires the user's explicit confirmation.",
            "approval",
            DeleteArgs,
            delete_document,
            permission="document.delete",
            approval_policy="self_confirm",
            approval_reason="Deleting records is irreversible.",
            describe=lambda a: f"Delete document {a.id} ({_short(a.reason, 60)})",
        ),
        Tool(
            "delete_campaign",
            "Request deletion of a campaign. Requires the user's explicit confirmation.",
            "approval",
            DeleteArgs,
            delete_campaign,
            permission="campaign.delete",
            approval_policy="self_confirm",
            approval_reason="Deleting records is irreversible.",
            describe=lambda a: f"Delete campaign {a.id} ({_short(a.reason, 60)})",
        ),
        Tool(
            "assign_role",
            "Request a role assignment for a colleague. Another administrator must approve.",
            "approval",
            AssignRoleArgs,
            assign_role,
            permission="role.manage",
            approval_policy="second_person",
            approval_reason="Permission changes need a second administrator.",
            describe=lambda a: (
                f"Give {a.user_email} the '{a.role}' role at {a.scope_type} scope"
                + (f" ({a.scope})" if a.scope else "")
            ),
        ),
    )
}


def available_tools(principal: Principal) -> list[Tool]:
    return [t for t in TOOLS.values() if t.available_to(principal)]
