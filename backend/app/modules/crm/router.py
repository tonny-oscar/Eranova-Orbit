import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.api.pagination import Page, PageParams, page_params
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.authorization.policy import is_allowed
from app.modules.crm import service
from app.modules.crm.models import Lead, LeadStatus
from app.modules.crm.schemas import (
    EnquiryOut,
    LeadDetail,
    LeadSummary,
    LeadUpdate,
    PersonRef,
    ProductRef,
)
from app.modules.identity.models import User
from app.modules.products.models import Product

router = APIRouter(prefix="/leads", tags=["crm"])


def _summary(lead: Lead, products: dict, users: dict) -> LeadSummary:
    product = products.get(lead.product_id)
    owner = users.get(lead.owner_user_id)
    return LeadSummary(
        id=lead.id,
        full_name=lead.full_name,
        organization=lead.organization,
        email=lead.email,
        phone=lead.phone,
        product=ProductRef(id=product.id, name=product.name) if product else None,
        source=lead.source,
        status=lead.status,
        priority=lead.priority,
        owner=PersonRef(id=owner.id, full_name=owner.full_name, email=owner.email)
        if owner
        else None,
        next_follow_up=lead.next_follow_up,
        last_enquiry_at=lead.last_enquiry_at,
        created_at=lead.created_at,
    )


async def _detail(db: AsyncSession, auth: AuthContext, lead: Lead) -> LeadDetail:
    products = await service.lookup(db, Product, {lead.product_id})
    users = await service.lookup(db, User, {lead.owner_user_id})
    enquiries = await service.list_enquiries(db, lead.id)
    return LeadDetail(
        **_summary(lead, products, users).model_dump(),
        notes=lead.notes,
        expected_value=lead.expected_value,
        currency=lead.currency,
        marketing_consent=lead.marketing_consent,
        enquiries=[EnquiryOut.model_validate(e, from_attributes=True) for e in enquiries],
        can_update=is_allowed(auth.principal, "lead.update", service.lead_context(lead)),
    )


@router.get("", response_model=Page[LeadSummary])
async def list_leads(
    q: str | None = Query(None, max_length=100),
    lead_status: LeadStatus | None = Query(None, alias="status"),
    product_id: uuid.UUID | None = None,
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("lead.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[LeadSummary]:
    leads, total = await service.list_leads(
        db,
        auth.principal,
        q=q,
        status=lead_status,
        product_id=product_id,
        limit=page.limit,
        offset=page.offset,
    )
    products = await service.lookup(db, Product, {lead.product_id for lead in leads})
    users = await service.lookup(db, User, {lead.owner_user_id for lead in leads})
    return Page(
        items=[_summary(lead, products, users) for lead in leads],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{lead_id}", response_model=LeadDetail)
async def get_lead(
    lead_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("lead.read")),
    db: AsyncSession = Depends(get_db),
) -> LeadDetail:
    return await _detail(db, auth, await service.get_lead(db, auth.principal, lead_id))


@router.patch("/{lead_id}", response_model=LeadDetail)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    auth: AuthContext = Depends(require_permission("lead.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> LeadDetail:
    lead = await service.update_lead(
        db, actor=auth.user, principal=auth.principal, lead_id=lead_id, payload=payload, meta=meta
    )
    return await _detail(db, auth, lead)
