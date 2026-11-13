"""Campaigns, the content workflow and the content calendar."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import ColumnElement, false, func, or_, select, true

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.db.base import utc_now
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed, scope_filter
from app.modules.crm.service import lookup
from app.modules.identity.models import User, UserStatus
from app.modules.marketing.models import (
    CAMPAIGN_STATUSES,
    CHANNELS,
    CONTENT_KINDS,
    Campaign,
    CampaignMetric,
    ContentItem,
)
from app.modules.notifications.service import notify
from app.modules.products.models import Product
from app.modules.products.service import escape_like

CampaignStatus = Literal[CAMPAIGN_STATUSES]  # type: ignore[valid-type]
ContentKind = Literal[CONTENT_KINDS]  # type: ignore[valid-type]
Channel = Literal[CHANNELS]  # type: ignore[valid-type]


# --- Schemas -------------------------------------------------------------------------


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class CampaignIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    product_id: uuid.UUID | None = None
    objective: str = Field(default="", max_length=5000)
    audience: str = Field(default="", max_length=5000)
    channels: list[Channel] = Field(default_factory=list, max_length=len(CHANNELS))
    budget_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    budget_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    start_date: date | None = None
    end_date: date | None = None
    status: CampaignStatus = "planned"
    owner_user_id: uuid.UUID | None = None
    notes: str = Field(default="", max_length=10_000)


class CampaignPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    objective: str | None = Field(default=None, max_length=5000)
    audience: str | None = Field(default=None, max_length=5000)
    channels: list[Channel] | None = Field(default=None, max_length=len(CHANNELS))
    budget_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    budget_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    start_date: date | None = None
    end_date: date | None = None
    status: CampaignStatus | None = None
    owner_user_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=10_000)


class MetricIn(BaseModel):
    metric: str = Field(min_length=2, max_length=60, pattern=r"^[A-Za-z0-9 _\-/%]+$")
    value: Decimal = Field(max_digits=18, decimal_places=2)
    period_start: date | None = None
    period_end: date | None = None
    source: str = Field(min_length=2, max_length=120)


class MetricOut(BaseModel):
    id: uuid.UUID
    metric: str
    value: Decimal
    period_start: date | None
    period_end: date | None
    source: str
    recorded_by: Ref | None
    created_at: datetime


class CampaignOut(BaseModel):
    id: uuid.UUID
    name: str
    product: Ref | None
    objective: str
    audience: str
    channels: list[str]
    budget_amount: Decimal | None
    budget_currency: str | None
    start_date: date | None
    end_date: date | None
    status: str
    owner: Ref | None
    notes: str
    content_counts: dict[str, int] = {}
    created_at: datetime
    can_update: bool = False


class CampaignDetail(CampaignOut):
    metrics: list[MetricOut]


class ContentIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    kind: ContentKind
    channel: Channel | None = None
    body: str = Field(default="", max_length=50_000)
    campaign_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None


class ContentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    channel: Channel | None = None
    body: str | None = Field(default=None, max_length=50_000)


class ContentAction(BaseModel):
    action: Literal[
        "submit",
        "approve",
        "request_changes",
        "schedule",
        "unschedule",
        "record_published",
        "record_failed",
        "reopen",
    ]
    note: str | None = Field(default=None, max_length=1000)
    scheduled_for: datetime | None = None
    published_url: HttpUrl | None = None
    published_at: datetime | None = None


class ContentOut(BaseModel):
    id: uuid.UUID
    title: str
    kind: str
    channel: str | None
    body: str
    status: str
    campaign: Ref | None
    product: Ref | None
    author: Ref | None
    approved_by: Ref | None
    approved_at: datetime | None
    review_note: str | None
    scheduled_for: datetime | None
    published_at: datetime | None
    published_url: str | None
    publish_method: str | None
    published_by: Ref | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    allowed_actions: list[str] = []
    can_edit: bool = False


# --- Access ----------------------------------------------------------------------------


def campaign_context(c: Campaign) -> ResourceContext:
    return ResourceContext(
        company_id=c.company_id,
        product_ids=frozenset({c.product_id}) if c.product_id else frozenset(),
        owner_user_id=c.owner_user_id,
    )


def content_context(item: ContentItem) -> ResourceContext:
    return ResourceContext(
        company_id=item.company_id,
        product_ids=frozenset({item.product_id}) if item.product_id else frozenset(),
        owner_user_id=item.author_user_id,
    )


def _scope(principal: Principal, product_col, owner_col, permission="campaign.read"):
    scope = scope_filter(principal, permission)
    if scope.company_wide:
        return true()
    conditions: list[ColumnElement[bool]] = []
    if scope.product_ids:
        conditions.append(product_col.in_(scope.product_ids))
    if scope.own:
        conditions.append(owner_col == principal.user_id)
    return or_(*conditions) if conditions else false()


def campaign_scope(principal: Principal) -> ColumnElement[bool]:
    return _scope(principal, Campaign.product_id, Campaign.owner_user_id)


def content_scope(principal: Principal) -> ColumnElement[bool]:
    return _scope(principal, ContentItem.product_id, ContentItem.author_user_id)


async def get_campaign(session, principal, campaign_id, permission="campaign.read") -> Campaign:
    c = await session.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id, Campaign.company_id == principal.company_id
        )
    )
    if c is None or not is_allowed(principal, "campaign.read", campaign_context(c)):
        raise NotFoundError("Campaign not found.")
    if permission != "campaign.read" and not is_allowed(principal, permission, campaign_context(c)):
        raise PermissionDeniedError("You cannot change this campaign.")
    return c


async def get_content(session, principal, content_id, permission="campaign.read") -> ContentItem:
    item = await session.scalar(
        select(ContentItem).where(
            ContentItem.id == content_id, ContentItem.company_id == principal.company_id
        )
    )
    if item is None or not is_allowed(principal, "campaign.read", content_context(item)):
        raise NotFoundError("Content not found.")
    if permission != "campaign.read" and not is_allowed(
        principal, permission, content_context(item)
    ):
        raise PermissionDeniedError("You cannot change this content.")
    return item


async def _check_refs(session, company_id, *, product_id=None, owner_user_id=None):
    if product_id and not await session.scalar(
        select(Product.id).where(Product.id == product_id, Product.company_id == company_id)
    ):
        raise AppError("Product not found.", code="invalid_product")
    if owner_user_id:
        user = await session.scalar(
            select(User).where(User.id == owner_user_id, User.company_id == company_id)
        )
        if user is None or user.status != UserStatus.ACTIVE:
            raise AppError("The selected owner is not an active user.", code="invalid_user")


async def _audit(
    session, actor: User, action: str, resource_type: str, resource_id, meta, details=None
):
    await record_event(
        session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type=resource_type,
        resource_id=resource_id,
        meta=meta,
        details=details or {},
    )


def _ref(obj, attr="name"):
    return Ref(id=obj.id, name=getattr(obj, attr)) if obj else None


# --- Campaigns ------------------------------------------------------------------------


async def list_campaigns(session, principal, *, q, status, product_id, limit, offset):
    conditions = [Campaign.company_id == principal.company_id, campaign_scope(principal)]
    if status:
        conditions.append(Campaign.status == status)
    if product_id:
        conditions.append(Campaign.product_id == product_id)
    if q and q.strip():
        conditions.append(
            func.lower(Campaign.name).like(f"%{escape_like(q.strip().lower())}%", escape="\\")
        )
    total = await session.scalar(select(func.count()).select_from(Campaign).where(*conditions))
    rows = await session.scalars(
        select(Campaign)
        .where(*conditions)
        .order_by(Campaign.start_date.desc().nulls_last(), Campaign.name)
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def campaign_outs(session, principal, campaigns: list[Campaign]) -> list[CampaignOut]:
    products = await lookup(session, Product, {c.product_id for c in campaigns})
    users = await lookup(session, User, {c.owner_user_id for c in campaigns})
    counts: dict = {}
    if campaigns:
        for cid, status, n in await session.execute(
            select(ContentItem.campaign_id, ContentItem.status, func.count())
            .where(ContentItem.campaign_id.in_([c.id for c in campaigns]))
            .group_by(ContentItem.campaign_id, ContentItem.status)
        ):
            counts.setdefault(cid, {})[status] = n
    return [
        CampaignOut(
            id=c.id,
            name=c.name,
            product=_ref(products.get(c.product_id)),
            objective=c.objective,
            audience=c.audience,
            channels=c.channels or [],
            budget_amount=c.budget_amount,
            budget_currency=c.budget_currency,
            start_date=c.start_date,
            end_date=c.end_date,
            status=c.status,
            owner=_ref(users.get(c.owner_user_id), "full_name"),
            notes=c.notes,
            content_counts=counts.get(c.id, {}),
            created_at=c.created_at,
            can_update=is_allowed(principal, "campaign.update", campaign_context(c)),
        )
        for c in campaigns
    ]


async def campaign_detail(session, principal, c: Campaign) -> CampaignDetail:
    out = (await campaign_outs(session, principal, [c]))[0]
    metrics = list(
        await session.scalars(
            select(CampaignMetric)
            .where(CampaignMetric.campaign_id == c.id)
            .order_by(
                CampaignMetric.period_end.desc().nulls_last(), CampaignMetric.created_at.desc()
            )
        )
    )
    users = await lookup(session, User, {m.recorded_by_user_id for m in metrics})
    return CampaignDetail(
        **out.model_dump(),
        metrics=[
            MetricOut(
                id=m.id,
                metric=m.metric,
                value=m.value,
                period_start=m.period_start,
                period_end=m.period_end,
                source=m.source,
                recorded_by=_ref(users.get(m.recorded_by_user_id), "full_name"),
                created_at=m.created_at,
            )
            for m in metrics
        ],
    )


def _validate_dates(start, end):
    if start and end and end < start:
        raise AppError("The end date must be on or after the start date.", code="invalid_dates")


async def create_campaign(session, actor, principal, payload: CampaignIn, meta) -> Campaign:
    context = ResourceContext(
        company_id=actor.company_id,
        product_ids=frozenset({payload.product_id}) if payload.product_id else frozenset(),
        owner_user_id=payload.owner_user_id or actor.id,
    )
    if not is_allowed(principal, "campaign.create", context):
        raise PermissionDeniedError("You cannot create campaigns for this product.")
    await _check_refs(
        session,
        actor.company_id,
        product_id=payload.product_id,
        owner_user_id=payload.owner_user_id,
    )
    _validate_dates(payload.start_date, payload.end_date)
    data = payload.model_dump()
    data["owner_user_id"] = data["owner_user_id"] or actor.id
    data["channels"] = sorted(set(data["channels"]))
    campaign = Campaign(company_id=actor.company_id, created_by_user_id=actor.id, **data)
    campaign.name = campaign.name.strip()
    session.add(campaign)
    await session.flush()
    await _audit(
        session, actor, "campaign.create", "campaign", campaign.id, meta, {"name": campaign.name}
    )
    await session.commit()
    return campaign


async def update_campaign(session, actor, principal, campaign_id, payload: CampaignPatch, meta):
    c = await get_campaign(session, principal, campaign_id, "campaign.update")
    changes = payload.model_dump(exclude_unset=True)
    for field in ("name", "status"):
        if field in changes and changes[field] is None:
            raise AppError(f"{field.title()} cannot be empty.", code="invalid_field")
    await _check_refs(session, actor.company_id, owner_user_id=changes.get("owner_user_id"))
    _validate_dates(changes.get("start_date", c.start_date), changes.get("end_date", c.end_date))
    for field, value in changes.items():
        if field in ("objective", "audience", "notes") and value is None:
            value = ""
        if field == "channels":
            value = sorted(set(value or []))
        setattr(c, field, value)
    await _audit(
        session, actor, "campaign.update", "campaign", c.id, meta, {"fields": sorted(changes)}
    )
    await session.commit()
    await session.refresh(c)
    return c


async def delete_campaign(session, actor, principal, campaign_id, meta) -> None:
    c = await get_campaign(session, principal, campaign_id, "campaign.delete")
    if await session.scalar(
        select(func.count())
        .select_from(ContentItem)
        .where(ContentItem.campaign_id == c.id, ContentItem.status == "published")
    ):
        raise AppError(
            "This campaign has published content. Mark it cancelled or completed instead.",
            code="campaign_has_published_content",
        )
    await _audit(session, actor, "campaign.delete", "campaign", c.id, meta, {"name": c.name})
    await session.delete(c)
    await session.commit()


async def add_metric(session, actor, principal, campaign_id, payload: MetricIn, meta) -> None:
    c = await get_campaign(session, principal, campaign_id, "campaign.update")
    _validate_dates(payload.period_start, payload.period_end)
    session.add(
        CampaignMetric(campaign_id=c.id, recorded_by_user_id=actor.id, **payload.model_dump())
    )
    await _audit(
        session,
        actor,
        "campaign.metric.add",
        "campaign",
        c.id,
        meta,
        {"metric": payload.metric, "source": payload.source},
    )
    await session.commit()


async def remove_metric(session, actor, principal, campaign_id, metric_id, meta) -> None:
    c = await get_campaign(session, principal, campaign_id, "campaign.update")
    metric = await session.scalar(
        select(CampaignMetric).where(
            CampaignMetric.id == metric_id, CampaignMetric.campaign_id == c.id
        )
    )
    if metric is None:
        raise NotFoundError("Metric not found.")
    await session.delete(metric)
    await _audit(session, actor, "campaign.metric.remove", "campaign", c.id, meta)
    await session.commit()


# --- Content workflow --------------------------------------------------------------------

# action -> (allowed from statuses, resulting status)
_TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "submit": (("draft",), "in_review"),
    "approve": (("in_review",), "approved"),
    "request_changes": (("in_review",), "draft"),
    "schedule": (("approved",), "scheduled"),
    "unschedule": (("scheduled",), "approved"),
    "record_published": (("approved", "scheduled", "failed"), "published"),
    "record_failed": (("approved", "scheduled"), "failed"),
    "reopen": (("approved", "scheduled", "failed"), "draft"),
}


def allowed_actions(principal: Principal, item: ContentItem) -> list[str]:
    context = content_context(item)
    can_update = is_allowed(principal, "campaign.update", context)
    can_approve = is_allowed(principal, "campaign.approve", context)
    actions = []
    for action, (sources, _) in _TRANSITIONS.items():
        if item.status not in sources:
            continue
        if action in ("approve", "request_changes"):
            # Reviewers cannot approve their own drafts.
            if can_approve and item.author_user_id != principal.user_id:
                actions.append(action)
        elif can_update:
            actions.append(action)
    return actions


def _resolve_product(item_product_id, campaign: Campaign | None):
    return campaign.product_id if campaign and campaign.product_id else item_product_id


async def list_content(
    session,
    principal,
    *,
    status=None,
    campaign_id=None,
    product_id=None,
    kind=None,
    start=None,
    end=None,
    limit=100,
    offset=0,
):
    conditions = [ContentItem.company_id == principal.company_id, content_scope(principal)]
    if status:
        conditions.append(ContentItem.status == status)
    if campaign_id:
        conditions.append(ContentItem.campaign_id == campaign_id)
    if product_id:
        conditions.append(ContentItem.product_id == product_id)
    if kind:
        conditions.append(ContentItem.kind == kind)
    when = func.coalesce(ContentItem.published_at, ContentItem.scheduled_for)
    if start:
        conditions.append(when >= start)
    if end:
        conditions.append(when < end)
    total = await session.scalar(select(func.count()).select_from(ContentItem).where(*conditions))
    rows = await session.scalars(
        select(ContentItem)
        .where(*conditions)
        .order_by(when.asc().nulls_last() if start or end else ContentItem.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def content_outs(session, principal, items: list[ContentItem]) -> list[ContentOut]:
    campaigns = await lookup(session, Campaign, {i.campaign_id for i in items})
    products = await lookup(session, Product, {i.product_id for i in items})
    users = await lookup(
        session,
        User,
        {i.author_user_id for i in items}
        | {i.approved_by_user_id for i in items}
        | {i.published_by_user_id for i in items},
    )
    return [
        ContentOut(
            id=i.id,
            title=i.title,
            kind=i.kind,
            channel=i.channel,
            body=i.body,
            status=i.status,
            campaign=_ref(campaigns.get(i.campaign_id)),
            product=_ref(products.get(i.product_id)),
            author=_ref(users.get(i.author_user_id), "full_name"),
            approved_by=_ref(users.get(i.approved_by_user_id), "full_name"),
            approved_at=i.approved_at,
            review_note=i.review_note,
            scheduled_for=i.scheduled_for,
            published_at=i.published_at,
            published_url=i.published_url,
            publish_method=i.publish_method,
            published_by=_ref(users.get(i.published_by_user_id), "full_name"),
            failure_reason=i.failure_reason,
            created_at=i.created_at,
            updated_at=i.updated_at,
            allowed_actions=allowed_actions(principal, i),
            can_edit=i.status in ("draft", "in_review")
            and is_allowed(principal, "campaign.update", content_context(i)),
        )
        for i in items
    ]


async def create_content(session, actor, principal, payload: ContentIn, meta) -> ContentItem:
    campaign = (
        await get_campaign(session, principal, payload.campaign_id) if payload.campaign_id else None
    )
    product_id = _resolve_product(payload.product_id, campaign)
    context = ResourceContext(
        company_id=actor.company_id,
        product_ids=frozenset({product_id}) if product_id else frozenset(),
        owner_user_id=actor.id,
    )
    if not is_allowed(principal, "campaign.create", context):
        raise PermissionDeniedError("You cannot create content for this product.")
    await _check_refs(session, actor.company_id, product_id=product_id)
    item = ContentItem(
        company_id=actor.company_id,
        campaign_id=campaign.id if campaign else None,
        product_id=product_id,
        kind=payload.kind,
        channel=payload.channel,
        title=payload.title.strip(),
        body=payload.body,
        author_user_id=actor.id,
    )
    session.add(item)
    await session.flush()
    await _audit(
        session, actor, "content_item.create", "content_item", item.id, meta, {"kind": item.kind}
    )
    await session.commit()
    return item


async def update_content(session, actor, principal, content_id, payload: ContentPatch, meta):
    item = await get_content(session, principal, content_id, "campaign.update")
    if item.status not in ("draft", "in_review"):
        raise AppError(
            "Approved content is locked. Reopen it as a draft to edit.", code="content_locked"
        )
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes and not changes["title"]:
        raise AppError("Title cannot be empty.", code="invalid_field")
    for field, value in changes.items():
        setattr(item, field, value if value is not None or field == "channel" else "")
    if item.status == "in_review":
        # Edits after submission send the item back so reviewers see the final text.
        item.status = "draft"
    await _audit(
        session,
        actor,
        "content_item.update",
        "content_item",
        item.id,
        meta,
        {"fields": sorted(changes)},
    )
    await session.commit()
    await session.refresh(item)
    return item


async def delete_content(session, actor, principal, content_id, meta) -> None:
    item = await get_content(session, principal, content_id, "campaign.delete")
    if item.status == "published":
        raise AppError("Published content is kept as a record.", code="content_published")
    await _audit(
        session, actor, "content_item.delete", "content_item", item.id, meta, {"title": item.title}
    )
    await session.delete(item)
    await session.commit()


async def act_on_content(session, actor, principal, content_id, payload: ContentAction, meta):
    item = await get_content(session, principal, content_id)
    if payload.action not in allowed_actions(principal, item):
        if payload.action == "approve" and item.author_user_id == actor.id:
            raise PermissionDeniedError("Someone other than the author must approve this content.")
        action = payload.action.replace("_", " ")
        raise AppError(
            f"'{action}' is not available while content is {item.status}.",
            code="invalid_transition",
        )
    now = utc_now()
    previous = item.status
    if payload.action == "schedule":
        if not payload.scheduled_for or payload.scheduled_for <= now:
            raise AppError("Choose a future date and time to schedule.", code="invalid_schedule")
        item.scheduled_for = payload.scheduled_for
    elif payload.action == "unschedule":
        item.scheduled_for = None
    elif payload.action == "approve":
        item.approved_by_user_id, item.approved_at = actor.id, now
        item.review_note = payload.note
    elif payload.action == "request_changes":
        if not payload.note:
            raise AppError("Explain what needs to change.", code="note_required")
        item.review_note = payload.note
        item.approved_by_user_id = item.approved_at = None
    elif payload.action == "record_published":
        if not payload.published_url:
            raise AppError(
                "Add the link to the live post so the publication can be verified.",
                code="published_url_required",
            )
        published_at = payload.published_at or now
        if published_at > now:
            raise AppError("Publication time cannot be in the future.", code="invalid_published_at")
        item.published_url = str(payload.published_url)
        item.published_at = published_at
        item.publish_method = "manual"
        item.published_by_user_id = actor.id
        item.failure_reason = None
    elif payload.action == "record_failed":
        if not payload.note:
            raise AppError("Describe why publishing failed.", code="note_required")
        item.failure_reason = payload.note
    elif payload.action == "reopen":
        item.approved_by_user_id = item.approved_at = None
        item.scheduled_for = None
    item.status = _TRANSITIONS[payload.action][1]
    await _audit(
        session,
        actor,
        f"content_item.{payload.action}",
        "content_item",
        item.id,
        meta,
        {"from": previous, "to": item.status},
    )
    if payload.action in ("approve", "request_changes") and item.author_user_id:
        await notify(
            session,
            company_id=item.company_id,
            user_ids=[item.author_user_id],
            kind=f"content.{payload.action}",
            title=("Approved" if payload.action == "approve" else "Changes requested")
            + f": {item.title}",
            body=payload.note,
            link=f"/app/marketing/content/{item.id}",
            exclude=actor.id,
        )
    await session.commit()
    await session.refresh(item)
    return item


async def calendar(session, principal, start: datetime, end: datetime) -> dict:
    items, _ = await list_content(session, principal, start=start, end=end, limit=500)
    campaigns = await session.scalars(
        select(Campaign).where(
            Campaign.company_id == principal.company_id,
            campaign_scope(principal),
            Campaign.status != "cancelled",
            or_(Campaign.start_date.is_(None), Campaign.start_date < end.date()),
            or_(Campaign.end_date.is_(None), Campaign.end_date >= start.date()),
            or_(Campaign.start_date.is_not(None), Campaign.end_date.is_not(None)),
        )
    )
    return {
        "content": await content_outs(session, principal, items),
        "campaigns": await campaign_outs(session, principal, list(campaigns)),
    }


async def overdue_scheduled(session) -> list[ContentItem]:
    """Scheduled content whose time has passed with no confirmed publication."""
    return list(
        await session.scalars(
            select(ContentItem).where(
                ContentItem.status == "scheduled", ContentItem.scheduled_for < utc_now()
            )
        )
    )
