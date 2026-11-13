import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.api.exports import csv_response, record_export
from app.api.pagination import Page, PageParams, page_params
from app.core.errors import AppError
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.marketing import service
from app.modules.marketing.service import (
    CampaignDetail,
    CampaignIn,
    CampaignOut,
    CampaignPatch,
    ContentAction,
    ContentIn,
    ContentOut,
    ContentPatch,
    MetricIn,
)

router = APIRouter(prefix="/marketing", tags=["marketing"])

READ = Depends(require_permission("campaign.read"))


@router.get("/campaigns", response_model=Page[CampaignOut])
async def list_campaigns(
    q: str | None = Query(None, max_length=100),
    campaign_status: str | None = Query(None, alias="status", max_length=20),
    product_id: uuid.UUID | None = None,
    page: PageParams = Depends(page_params),
    auth: AuthContext = READ,
    db: AsyncSession = Depends(get_db),
) -> Page[CampaignOut]:
    rows, total = await service.list_campaigns(
        db,
        auth.principal,
        q=q,
        status=campaign_status,
        product_id=product_id,
        limit=page.limit,
        offset=page.offset,
    )
    items = await service.campaign_outs(db, auth.principal, rows)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("/campaigns", response_model=CampaignDetail, status_code=201)
async def create_campaign(
    payload: CampaignIn,
    auth: AuthContext = Depends(require_permission("campaign.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CampaignDetail:
    c = await service.create_campaign(db, auth.user, auth.principal, payload, meta)
    return await service.campaign_detail(db, auth.principal, c)


@router.get("/campaigns/export.csv")
async def export_campaigns(
    auth: AuthContext = Depends(require_permission("campaign.export")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    rows, _ = await service.list_campaigns(
        db, auth.principal, q=None, status=None, product_id=None, limit=10_000, offset=0
    )
    outs = await service.campaign_outs(db, auth.principal, rows)
    await record_export(db, auth, "campaigns", len(outs), meta)
    return csv_response(
        "campaigns.csv",
        [
            "Name",
            "Product",
            "Status",
            "Channels",
            "Start",
            "End",
            "Budget",
            "Currency",
            "Owner",
            "Published content",
        ],
        [
            [
                c.name,
                c.product.name if c.product else "",
                c.status,
                ", ".join(c.channels),
                c.start_date,
                c.end_date,
                c.budget_amount,
                c.budget_currency,
                c.owner.name if c.owner else "",
                c.content_counts.get("published", 0),
            ]
            for c in outs
        ],
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(
    campaign_id: uuid.UUID, auth: AuthContext = READ, db: AsyncSession = Depends(get_db)
) -> CampaignDetail:
    c = await service.get_campaign(db, auth.principal, campaign_id)
    return await service.campaign_detail(db, auth.principal, c)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignDetail)
async def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignPatch,
    auth: AuthContext = Depends(require_permission("campaign.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CampaignDetail:
    c = await service.update_campaign(db, auth.user, auth.principal, campaign_id, payload, meta)
    return await service.campaign_detail(db, auth.principal, c)


@router.delete("/campaigns/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("campaign.delete")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.delete_campaign(db, auth.user, auth.principal, campaign_id, meta)
    return Response(status_code=204)


@router.post("/campaigns/{campaign_id}/metrics", response_model=CampaignDetail, status_code=201)
async def add_metric(
    campaign_id: uuid.UUID,
    payload: MetricIn,
    auth: AuthContext = Depends(require_permission("campaign.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CampaignDetail:
    await service.add_metric(db, auth.user, auth.principal, campaign_id, payload, meta)
    c = await service.get_campaign(db, auth.principal, campaign_id)
    return await service.campaign_detail(db, auth.principal, c)


@router.delete("/campaigns/{campaign_id}/metrics/{metric_id}", status_code=204)
async def remove_metric(
    campaign_id: uuid.UUID,
    metric_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("campaign.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.remove_metric(db, auth.user, auth.principal, campaign_id, metric_id, meta)
    return Response(status_code=204)


@router.get("/content", response_model=Page[ContentOut])
async def list_content(
    content_status: str | None = Query(None, alias="status", max_length=20),
    campaign_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    kind: str | None = Query(None, max_length=30),
    page: PageParams = Depends(page_params),
    auth: AuthContext = READ,
    db: AsyncSession = Depends(get_db),
) -> Page[ContentOut]:
    rows, total = await service.list_content(
        db,
        auth.principal,
        status=content_status,
        campaign_id=campaign_id,
        product_id=product_id,
        kind=kind,
        limit=page.limit,
        offset=page.offset,
    )
    items = await service.content_outs(db, auth.principal, rows)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("/content", response_model=ContentOut, status_code=201)
async def create_content(
    payload: ContentIn,
    auth: AuthContext = Depends(require_permission("campaign.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ContentOut:
    item = await service.create_content(db, auth.user, auth.principal, payload, meta)
    return (await service.content_outs(db, auth.principal, [item]))[0]


@router.get("/content/{content_id}", response_model=ContentOut)
async def get_content(
    content_id: uuid.UUID, auth: AuthContext = READ, db: AsyncSession = Depends(get_db)
) -> ContentOut:
    item = await service.get_content(db, auth.principal, content_id)
    return (await service.content_outs(db, auth.principal, [item]))[0]


@router.patch("/content/{content_id}", response_model=ContentOut)
async def update_content(
    content_id: uuid.UUID,
    payload: ContentPatch,
    auth: AuthContext = Depends(require_permission("campaign.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ContentOut:
    item = await service.update_content(db, auth.user, auth.principal, content_id, payload, meta)
    return (await service.content_outs(db, auth.principal, [item]))[0]


@router.delete("/content/{content_id}", status_code=204)
async def delete_content(
    content_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("campaign.delete")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.delete_content(db, auth.user, auth.principal, content_id, meta)
    return Response(status_code=204)


@router.post("/content/{content_id}/actions", response_model=ContentOut)
async def content_action(
    content_id: uuid.UUID,
    payload: ContentAction,
    auth: AuthContext = READ,
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ContentOut:
    item = await service.act_on_content(db, auth.user, auth.principal, content_id, payload, meta)
    return (await service.content_outs(db, auth.principal, [item]))[0]


@router.get("/calendar")
async def calendar(
    start: datetime,
    end: datetime,
    auth: AuthContext = READ,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if end <= start or end - start > timedelta(days=93):
        raise AppError("Choose a calendar range of up to three months.", code="invalid_range")
    return await service.calendar(db, auth.principal, start, end)
