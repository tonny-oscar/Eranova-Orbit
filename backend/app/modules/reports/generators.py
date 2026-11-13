"""Report generators.

Every figure is computed from records the principal may read, using the same
scope rules as the module screens. Sections the principal has no permission
for are omitted rather than shown as zero.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.modules.authorization.policy import Principal, scope_filter
from app.modules.crm.models import Customer, CustomerProduct, Lead, PipelineStage
from app.modules.crm.service import _scope_condition as lead_scope
from app.modules.identity.models import User, UserStatus
from app.modules.integrations.models import IntegrationConnection, IntegrationRecord
from app.modules.integrations.service import scope_condition as integration_scope
from app.modules.marketing.models import Campaign, ContentItem
from app.modules.marketing.service import campaign_scope, content_scope
from app.modules.people.models import AttendanceRecord, Department, EmployeeProfile, LeaveRequest
from app.modules.people.service import department_member_condition
from app.modules.products.models import Product
from app.modules.products.service import product_scope_condition
from app.modules.support.models import SupportTicket
from app.modules.support.service import OPEN_STATUSES as OPEN_TICKETS
from app.modules.support.service import ticket_scope
from app.modules.work.models import Project, Task
from app.modules.work.service import OPEN_STATUSES as OPEN_TASKS
from app.modules.work.service import task_scope


@dataclass
class Period:
    start: date
    end: date  # inclusive

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.start, time.min, tzinfo=UTC)

    @property
    def end_at(self) -> datetime:
        return datetime.combine(self.end + timedelta(days=1), time.min, tzinfo=UTC)


@dataclass
class Section:
    title: str
    metrics: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    note: str | None = None

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "metrics": self.metrics,
            "columns": self.columns,
            "rows": self.rows,
            "note": self.note,
        }


def _metric(label: str, value, unit: str | None = None) -> dict:
    return {"label": label, "value": value, "unit": unit}


def _can(principal: Principal, permission: str) -> bool:
    return not scope_filter(principal, permission).is_empty


async def _count(session, model, *conditions) -> int:
    return await session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


Generator = Callable[[AsyncSession, Principal, Period, uuid.UUID | None], Awaitable[list[Section]]]


# --- Section builders ------------------------------------------------------------------------


async def _products_section(session, principal, period, product_id) -> Section:
    cond = [
        Product.company_id == principal.company_id,
        product_scope_condition(scope_filter(principal, "product.read"), principal.user_id),
    ]
    if product_id:
        cond.append(Product.id == product_id)
    rows = (
        await session.execute(
            select(Product.lifecycle_status, func.count())
            .where(*cond)
            .group_by(Product.lifecycle_status)
        )
    ).all()
    return Section(
        "Products",
        metrics=[_metric("Products", sum(n for _, n in rows))]
        + [_metric(status.replace("_", " ").title(), n) for status, n in sorted(rows)],
    )


async def _sales_summary(session, principal, period, product_id) -> Section:
    cond = [Lead.company_id == principal.company_id, lead_scope(principal)]
    if product_id:
        cond.append(Lead.product_id == product_id)
    created = await _count(
        session, Lead, *cond, Lead.created_at >= period.start_at, Lead.created_at < period.end_at
    )
    converted = await _count(
        session,
        Lead,
        *cond,
        Lead.converted_at >= period.start_at,
        Lead.converted_at < period.end_at,
    )
    overdue = await _count(
        session,
        Lead,
        *cond,
        Lead.next_follow_up < date.today(),
        Lead.converted_customer_id.is_(None),
    )
    return Section(
        "Sales",
        metrics=[
            _metric("New leads", created),
            _metric("Converted to customers", converted),
            _metric("Overdue follow-ups (now)", overdue),
        ],
    )


async def _delivery_summary(session, principal, period, product_id) -> Section:
    cond = [Task.company_id == principal.company_id, task_scope(principal)]
    if product_id:
        cond.append(Task.project_id.in_(select(Project.id).where(Project.product_id == product_id)))
    return Section(
        "Delivery",
        metrics=[
            _metric(
                "Open tasks (now)", await _count(session, Task, *cond, Task.status.in_(OPEN_TASKS))
            ),
            _metric(
                "Overdue tasks (now)",
                await _count(
                    session, Task, *cond, Task.status.in_(OPEN_TASKS), Task.due_date < date.today()
                ),
            ),
            _metric(
                "Completed in period",
                await _count(
                    session,
                    Task,
                    *cond,
                    Task.completed_at >= period.start_at,
                    Task.completed_at < period.end_at,
                ),
            ),
        ],
    )


async def _support_summary(session, principal, period, product_id) -> Section:
    cond = [SupportTicket.company_id == principal.company_id, ticket_scope(principal)]
    if product_id:
        cond.append(SupportTicket.product_id == product_id)
    return Section(
        "Support",
        metrics=[
            _metric(
                "Open tickets (now)",
                await _count(session, SupportTicket, *cond, SupportTicket.status.in_(OPEN_TICKETS)),
            ),
            _metric(
                "Created in period",
                await _count(
                    session,
                    SupportTicket,
                    *cond,
                    SupportTicket.created_at >= period.start_at,
                    SupportTicket.created_at < period.end_at,
                ),
            ),
            _metric(
                "Resolved in period",
                await _count(
                    session,
                    SupportTicket,
                    *cond,
                    SupportTicket.resolved_at >= period.start_at,
                    SupportTicket.resolved_at < period.end_at,
                ),
            ),
        ],
    )


async def _marketing_summary(session, principal, period, product_id) -> Section:
    c_cond = [Campaign.company_id == principal.company_id, campaign_scope(principal)]
    i_cond = [ContentItem.company_id == principal.company_id, content_scope(principal)]
    if product_id:
        c_cond.append(Campaign.product_id == product_id)
        i_cond.append(ContentItem.product_id == product_id)
    return Section(
        "Marketing",
        metrics=[
            _metric(
                "Active campaigns (now)",
                await _count(session, Campaign, *c_cond, Campaign.status == "active"),
            ),
            _metric(
                "Content published in period",
                await _count(
                    session,
                    ContentItem,
                    *i_cond,
                    ContentItem.status == "published",
                    ContentItem.published_at >= period.start_at,
                    ContentItem.published_at < period.end_at,
                ),
            ),
            _metric(
                "Awaiting review (now)",
                await _count(session, ContentItem, *i_cond, ContentItem.status == "in_review"),
            ),
        ],
    )


# --- Reports ------------------------------------------------------------------------------------


async def executive(session, principal, period, product_id) -> list[Section]:
    sections = []
    for permission, builder in (
        ("product.read", _products_section),
        ("lead.read", _sales_summary),
        ("task.read", _delivery_summary),
        ("ticket.read", _support_summary),
        ("campaign.read", _marketing_summary),
    ):
        if _can(principal, permission):
            sections.append(await builder(session, principal, period, product_id))
    return sections


async def sales(session, principal, period, product_id) -> list[Section]:
    cond = [Lead.company_id == principal.company_id, lead_scope(principal)]
    if product_id:
        cond.append(Lead.product_id == product_id)
    in_period = [*cond, Lead.created_at >= period.start_at, Lead.created_at < period.end_at]
    stages = {
        s.key: s.name
        for s in await session.scalars(
            select(PipelineStage).where(PipelineStage.company_id == principal.company_id)
        )
    }
    by_source = (
        await session.execute(
            select(Lead.source, func.count())
            .where(*in_period)
            .group_by(Lead.source)
            .order_by(func.count().desc())
        )
    ).all()
    by_stage = (
        await session.execute(
            select(Lead.status, func.count()).where(*in_period).group_by(Lead.status)
        )
    ).all()
    by_product = (
        await session.execute(
            select(func.coalesce(Product.name, "No product"), func.count())
            .select_from(Lead)
            .outerjoin(Product, Product.id == Lead.product_id)
            .where(*in_period)
            .group_by(Product.name)
        )
    ).all()
    overdue = (
        await session.execute(
            select(Lead.full_name, Lead.organization, Lead.next_follow_up, User.full_name)
            .outerjoin(User, User.id == Lead.owner_user_id)
            .where(*cond, Lead.next_follow_up < date.today(), Lead.converted_customer_id.is_(None))
            .order_by(Lead.next_follow_up)
            .limit(100)
        )
    ).all()
    summary = await _sales_summary(session, principal, period, product_id)
    created = summary.metrics[0]["value"]
    converted = summary.metrics[1]["value"]
    summary.metrics.append(
        _metric(
            "Conversion rate (converted ÷ new)",
            round(100 * converted / created, 1) if created else None,
            "%",
        )
    )
    return [
        summary,
        Section(
            "New leads by source", columns=["Source", "Leads"], rows=[[s, n] for s, n in by_source]
        ),
        Section(
            "New leads by current stage",
            columns=["Stage", "Leads"],
            rows=[[stages.get(k, k), n] for k, n in by_stage],
        ),
        Section(
            "New leads by product", columns=["Product", "Leads"], rows=[list(r) for r in by_product]
        ),
        Section(
            "Overdue follow-ups",
            columns=["Lead", "Organisation", "Follow-up date", "Owner"],
            rows=[[a, b, c, d or "Unassigned"] for a, b, c, d in overdue],
        ),
    ]


async def support(session, principal, period, product_id) -> list[Section]:
    cond = [SupportTicket.company_id == principal.company_id, ticket_scope(principal)]
    if product_id:
        cond.append(SupportTicket.product_id == product_id)
    created = [
        *cond,
        SupportTicket.created_at >= period.start_at,
        SupportTicket.created_at < period.end_at,
    ]

    def median_hours(end_col):
        hours = extract("epoch", end_col - SupportTicket.created_at) / 3600
        return select(func.percentile_cont(0.5).within_group(hours)).where(
            *created, end_col.is_not(None)
        )

    first = await session.scalar(median_hours(SupportTicket.first_response_at))
    resolution = await session.scalar(median_hours(SupportTicket.resolved_at))
    summary = await _support_summary(session, principal, period, product_id)
    summary.metrics += [
        _metric("Median first response", round(first, 1) if first is not None else None, "hours"),
        _metric(
            "Median time to resolve",
            round(resolution, 1) if resolution is not None else None,
            "hours",
        ),
    ]
    by_category = (
        await session.execute(
            select(SupportTicket.category, func.count())
            .where(*created)
            .group_by(SupportTicket.category)
        )
    ).all()
    by_priority = (
        await session.execute(
            select(SupportTicket.priority, func.count())
            .where(*created)
            .group_by(SupportTicket.priority)
        )
    ).all()
    aging = (
        await session.execute(
            select(
                SupportTicket.number,
                SupportTicket.subject,
                SupportTicket.status,
                SupportTicket.priority,
                SupportTicket.created_at,
                User.full_name,
            )
            .outerjoin(User, User.id == SupportTicket.assignee_user_id)
            .where(*cond, SupportTicket.status.in_(OPEN_TICKETS))
            .order_by(SupportTicket.created_at)
            .limit(100)
        )
    ).all()
    now = utc_now()
    return [
        summary,
        Section(
            "Tickets by category",
            columns=["Category", "Tickets"],
            rows=[list(r) for r in by_category],
        ),
        Section(
            "Tickets by priority",
            columns=["Priority", "Tickets"],
            rows=[list(r) for r in by_priority],
        ),
        Section(
            "Open tickets by age",
            columns=["Ticket", "Subject", "Status", "Priority", "Age (days)", "Assignee"],
            rows=[
                [f"T-{n}", s, st, p, (now - c).days, a or "Unassigned"]
                for n, s, st, p, c, a in aging
            ],
        ),
    ]


async def delivery(session, principal, period, product_id) -> list[Section]:
    cond = [Task.company_id == principal.company_id, task_scope(principal)]
    if product_id:
        cond.append(Task.project_id.in_(select(Project.id).where(Project.product_id == product_id)))
    completed_by = (
        await session.execute(
            select(func.coalesce(User.full_name, "Unassigned"), func.count())
            .select_from(Task)
            .outerjoin(User, User.id == Task.assignee_user_id)
            .where(*cond, Task.completed_at >= period.start_at, Task.completed_at < period.end_at)
            .group_by(User.full_name)
            .order_by(func.count().desc())
        )
    ).all()
    by_project = (
        await session.execute(
            select(
                Project.name,
                func.count().filter(Task.status.in_(OPEN_TASKS)),
                func.count().filter(
                    and_(Task.status.in_(OPEN_TASKS), Task.due_date < date.today())
                ),
                func.count().filter(
                    and_(Task.completed_at >= period.start_at, Task.completed_at < period.end_at)
                ),
            )
            .join(Project, Project.id == Task.project_id)
            .where(*cond)
            .group_by(Project.name)
            .order_by(Project.name)
        )
    ).all()
    by_status = (
        await session.execute(
            select(Task.status, func.count())
            .where(*cond, Task.status.in_(OPEN_TASKS))
            .group_by(Task.status)
        )
    ).all()
    return [
        await _delivery_summary(session, principal, period, product_id),
        Section(
            "Projects",
            columns=["Project", "Open tasks", "Overdue", "Completed in period"],
            rows=[list(r) for r in by_project],
        ),
        Section(
            "Open tasks by status",
            columns=["Status", "Tasks"],
            rows=[[s.replace("_", " "), n] for s, n in by_status],
        ),
        Section(
            "Completed in period by assignee",
            columns=["Assignee", "Tasks"],
            rows=[list(r) for r in completed_by],
        ),
    ]


async def marketing(session, principal, period, product_id) -> list[Section]:
    c_cond = [Campaign.company_id == principal.company_id, campaign_scope(principal)]
    i_cond = [ContentItem.company_id == principal.company_id, content_scope(principal)]
    if product_id:
        c_cond.append(Campaign.product_id == product_id)
        i_cond.append(ContentItem.product_id == product_id)
    campaigns = (
        await session.execute(
            select(
                Campaign.name,
                Campaign.status,
                Campaign.start_date,
                Campaign.end_date,
                Campaign.budget_amount,
                Campaign.budget_currency,
            )
            .where(
                *c_cond,
                (Campaign.start_date.is_(None)) | (Campaign.start_date <= period.end),
                (Campaign.end_date.is_(None)) | (Campaign.end_date >= period.start),
            )
            .order_by(Campaign.start_date.nulls_last())
        )
    ).all()
    by_status = (
        await session.execute(
            select(ContentItem.status, func.count()).where(*i_cond).group_by(ContentItem.status)
        )
    ).all()
    published = (
        await session.execute(
            select(
                ContentItem.title,
                ContentItem.channel,
                ContentItem.published_at,
                ContentItem.publish_method,
                ContentItem.published_url,
            )
            .where(
                *i_cond,
                ContentItem.status == "published",
                ContentItem.published_at >= period.start_at,
                ContentItem.published_at < period.end_at,
            )
            .order_by(ContentItem.published_at)
        )
    ).all()
    return [
        await _marketing_summary(session, principal, period, product_id),
        Section(
            "Campaigns running in period",
            columns=["Campaign", "Status", "Start", "End", "Budget", "Currency"],
            rows=[list(r) for r in campaigns],
        ),
        Section(
            "Content by status (now)",
            columns=["Status", "Items"],
            rows=[list(r) for r in by_status],
        ),
        Section(
            "Published in period",
            columns=["Title", "Channel", "Published", "Confirmed by", "Link"],
            rows=[
                [t, ch, p, "staff (manual)" if m == "manual" else "provider", url]
                for t, ch, p, m, url in published
            ],
            note=(
                "Only publications confirmed by a connected provider or recorded by staff "
                "with a link are counted."
            ),
        ),
    ]


async def traffic(session, principal, period, product_id) -> list[Section]:
    p_cond = [
        Product.company_id == principal.company_id,
        product_scope_condition(scope_filter(principal, "product.read"), principal.user_id),
    ]
    if product_id:
        p_cond.append(Product.id == product_id)
    keys = ("activeUsers", "sessions", "screenPageViews", "conversions")
    start_key, end_key = period.start.strftime("%Y%m%d"), period.end.strftime("%Y%m%d")
    rows = (
        await session.execute(
            select(
                Product.name,
                IntegrationConnection.name,
                IntegrationConnection.last_success_at,
                IntegrationRecord.data,
            )
            .join(IntegrationConnection, IntegrationConnection.product_id == Product.id)
            .join(IntegrationRecord, IntegrationRecord.connection_id == IntegrationConnection.id)
            .where(
                *p_cond,
                IntegrationConnection.provider == "ga4",
                IntegrationRecord.kind == "traffic_daily",
                IntegrationRecord.external_id >= start_key,
                IntegrationRecord.external_id <= end_key,
            )
        )
    ).all()
    totals: dict[str, dict] = {}
    for product, source, updated, data in rows:
        entry = totals.setdefault(
            product, {"source": source, "updated": updated, **dict.fromkeys(keys, 0)}
        )
        for k in keys:
            entry[k] += data.get(k) or 0
    return [
        Section(
            "Website traffic by product",
            columns=[
                "Product",
                "Active users",
                "Sessions",
                "Page views",
                "Conversions",
                "Source",
                "Last updated",
            ],
            rows=[
                [name, *(e[k] for k in keys), e["source"], e["updated"]]
                for name, e in sorted(totals.items())
            ],
            note=None
            if rows
            else "No Google Analytics data for this period. Connect GA4 under Integrations.",
        )
    ]


async def product(session, principal, period, product_id) -> list[Section]:
    cond = [
        Product.company_id == principal.company_id,
        product_scope_condition(scope_filter(principal, "product.read"), principal.user_id),
    ]
    if product_id:
        cond.append(Product.id == product_id)
    products = list(await session.scalars(select(Product).where(*cond).order_by(Product.name)))
    ids = [p.id for p in products]
    columns = ["Product", "Status"]
    stats: dict[str, dict] = {}

    async def grouped(label, query):
        columns.append(label)
        stats[label] = dict((await session.execute(query)).all()) if ids else {}

    if _can(principal, "customer.read"):
        await grouped(
            "Active subscriptions",
            select(CustomerProduct.product_id, func.count())
            .join(Customer, Customer.id == CustomerProduct.customer_id)
            .where(
                CustomerProduct.product_id.in_(ids), CustomerProduct.status.in_(("trial", "active"))
            )
            .group_by(CustomerProduct.product_id),
        )
    if _can(principal, "task.read"):
        await grouped(
            "Open tasks",
            select(Project.product_id, func.count())
            .select_from(Task)
            .join(Project, Project.id == Task.project_id)
            .where(Project.product_id.in_(ids), Task.status.in_(OPEN_TASKS), task_scope(principal))
            .group_by(Project.product_id),
        )
    if _can(principal, "ticket.read"):
        await grouped(
            "Open tickets",
            select(SupportTicket.product_id, func.count())
            .where(
                SupportTicket.product_id.in_(ids),
                SupportTicket.status.in_(OPEN_TICKETS),
                ticket_scope(principal),
            )
            .group_by(SupportTicket.product_id),
        )
    if _can(principal, "integration.read"):
        columns.append("Integrations failing")
        stats["Integrations failing"] = (
            dict(
                (
                    await session.execute(
                        select(IntegrationConnection.product_id, func.count())
                        .where(
                            IntegrationConnection.product_id.in_(ids),
                            IntegrationConnection.status == "error",
                            integration_scope(principal),
                        )
                        .group_by(IntegrationConnection.product_id)
                    )
                ).all()
            )
            if ids
            else {}
        )
    rows = [
        [p.name, p.lifecycle_status, *(stats[label].get(p.id, 0) for label in columns[2:])]
        for p in products
    ]
    return [Section("Products", columns=columns, rows=rows)]


async def people(session, principal, period, product_id) -> list[Section]:
    members = department_member_condition(principal, "employee.read")
    headcount = (
        await session.execute(
            select(func.coalesce(Department.name, "No department"), func.count())
            .select_from(User)
            .outerjoin(EmployeeProfile, EmployeeProfile.user_id == User.id)
            .outerjoin(Department, Department.id == EmployeeProfile.department_id)
            .where(
                User.company_id == principal.company_id, User.status == UserStatus.ACTIVE, members
            )
            .group_by(Department.name)
            .order_by(Department.name)
        )
    ).all()
    member_ids = (
        select(User.id)
        .outerjoin(EmployeeProfile, EmployeeProfile.user_id == User.id)
        .where(User.company_id == principal.company_id, members)
    )
    days = (
        func.least(LeaveRequest.end_date, period.end)
        - func.greatest(LeaveRequest.start_date, period.start)
        + 1
    )
    leave = (
        await session.execute(
            select(LeaveRequest.type, func.count(), func.sum(days))
            .where(
                LeaveRequest.user_id.in_(member_ids),
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= period.end,
                LeaveRequest.end_date >= period.start,
            )
            .group_by(LeaveRequest.type)
        )
    ).all()
    attendance_days = await _count(
        session,
        AttendanceRecord,
        AttendanceRecord.user_id.in_(member_ids),
        AttendanceRecord.work_date >= period.start,
        AttendanceRecord.work_date <= period.end,
    )
    return [
        Section(
            "Headcount by department",
            columns=["Department", "Active staff"],
            rows=[list(r) for r in headcount],
        ),
        Section(
            "Approved leave overlapping the period",
            columns=["Type", "Requests", "Calendar days in period"],
            rows=[[t, n, int(d or 0)] for t, n, d in leave],
        ),
        Section(
            "Attendance",
            metrics=[_metric("Self-reported check-in days", attendance_days)],
            note="Aggregated only. Attendance is self-reported check-in; Orbit does no monitoring.",
        ),
    ]


@dataclass(frozen=True)
class ReportDef:
    key: str
    title: str
    description: str
    permission: str | None
    generator: Generator


REPORTS: dict[str, ReportDef] = {
    r.key: r
    for r in (
        ReportDef(
            "executive",
            "Executive summary",
            "Headline figures across every area you can see.",
            None,
            executive,
        ),
        ReportDef(
            "sales",
            "Sales",
            "Leads, conversions, sources and overdue follow-ups.",
            "lead.read",
            sales,
        ),
        ReportDef(
            "support",
            "Support",
            "Ticket volumes, response and resolution times, ageing.",
            "ticket.read",
            support,
        ),
        ReportDef(
            "delivery",
            "Delivery",
            "Projects, open and overdue tasks, completed work.",
            "task.read",
            delivery,
        ),
        ReportDef(
            "marketing",
            "Marketing",
            "Campaigns, content pipeline and confirmed publications.",
            "campaign.read",
            marketing,
        ),
        ReportDef(
            "traffic",
            "Website traffic",
            "Google Analytics totals per product.",
            "product.read",
            traffic,
        ),
        ReportDef(
            "product",
            "Products",
            "Per-product subscriptions, work, support and integration health.",
            "product.read",
            product,
        ),
        ReportDef(
            "people",
            "People",
            "Headcount, leave and attendance in aggregate.",
            "employee.read",
            people,
        ),
    )
}


def available(principal: Principal) -> list[ReportDef]:
    return [r for r in REPORTS.values() if r.permission is None or _can(principal, r.permission)]


async def generate(session, principal, key: str, period: Period, product_id=None) -> dict:
    report = REPORTS[key]
    sections = await report.generator(session, principal, period, product_id)
    return {
        "key": report.key,
        "title": report.title,
        "period": {"start": period.start.isoformat(), "end": period.end.isoformat()},
        "product_id": str(product_id) if product_id else None,
        "generated_at": utc_now().isoformat(),
        "sections": [s.as_dict() for s in sections],
    }
