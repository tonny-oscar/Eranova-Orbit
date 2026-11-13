import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.api.exports import csv_response, record_export
from app.api.pagination import Page, PageParams, page_params
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.authorization.policy import ResourceContext, is_allowed
from app.modules.crm import customers as customer_service
from app.modules.crm import pipeline, service
from app.modules.crm.customers import (
    ActivityIn,
    ContactIn,
    CustomerDetail,
    CustomerIn,
    CustomerPatch,
    CustomerSummary,
    SubscriptionIn,
)
from app.modules.crm.models import Customer, Lead
from app.modules.crm.schemas import (
    EnquiryOut,
    LeadConvert,
    LeadCreate,
    LeadDetail,
    LeadSummary,
    LeadUpdate,
    PersonRef,
    ProductRef,
)
from app.modules.identity.models import User
from app.modules.products.models import Product

router = APIRouter(tags=["crm"])


# --- Leads ----------------------------------------------------------------------


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
    customers = await service.lookup(db, Customer, {lead.converted_customer_id})
    customer = customers.get(lead.converted_customer_id)
    enquiries = await service.list_enquiries(db, lead.id)
    activities = await customer_service.activities_for(db, lead_ids=[lead.id], customer_id=None)
    can_update = is_allowed(auth.principal, "lead.update", service.lead_context(lead))
    return LeadDetail(
        **_summary(lead, products, users).model_dump(),
        notes=lead.notes,
        expected_value=lead.expected_value,
        currency=lead.currency,
        marketing_consent=lead.marketing_consent,
        enquiries=[EnquiryOut.model_validate(e, from_attributes=True) for e in enquiries],
        activities=[a.model_dump(mode="json") for a in activities],
        converted_customer=ProductRef(id=customer.id, name=customer.name) if customer else None,
        converted_at=lead.converted_at,
        can_update=can_update,
        can_convert=can_update
        and lead.converted_customer_id is None
        and is_allowed(
            auth.principal, "customer.create", ResourceContext(company_id=lead.company_id)
        ),
    )


@router.get("/leads", response_model=Page[LeadSummary])
async def list_leads(
    q: str | None = Query(None, max_length=100),
    lead_status: str | None = Query(None, alias="status", max_length=30),
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


@router.post("/leads", response_model=LeadDetail, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    auth: AuthContext = Depends(require_permission("lead.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> LeadDetail:
    lead = await service.create_lead(
        db, actor=auth.user, principal=auth.principal, payload=payload, meta=meta
    )
    return await _detail(db, auth, lead)


@router.get("/leads/export.csv")
async def export_leads(
    auth: AuthContext = Depends(require_permission("lead.export")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    leads, _ = await service.list_leads(
        db, auth.principal, q=None, status=None, product_id=None, limit=10_000, offset=0
    )
    products = await service.lookup(db, Product, {lead.product_id for lead in leads})
    await record_export(db, auth, "leads", len(leads), meta)
    return csv_response(
        "leads.csv",
        [
            "Name",
            "Organisation",
            "Email",
            "Phone",
            "Product",
            "Status",
            "Priority",
            "Source",
            "Next follow-up",
            "Created",
        ],
        [
            [
                lead.full_name,
                lead.organization,
                lead.email,
                lead.phone,
                products[lead.product_id].name if lead.product_id in products else "",
                lead.status,
                lead.priority,
                lead.source,
                lead.next_follow_up,
                lead.created_at,
            ]
            for lead in leads
        ],
    )


@router.get("/leads/{lead_id}", response_model=LeadDetail)
async def get_lead(
    lead_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("lead.read")),
    db: AsyncSession = Depends(get_db),
) -> LeadDetail:
    return await _detail(db, auth, await service.get_lead(db, auth.principal, lead_id))


@router.patch("/leads/{lead_id}", response_model=LeadDetail)
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


@router.post("/leads/{lead_id}/activities", response_model=LeadDetail, status_code=201)
async def add_lead_activity(
    lead_id: uuid.UUID,
    payload: ActivityIn,
    auth: AuthContext = Depends(require_permission("lead.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> LeadDetail:
    await service.add_lead_activity(
        db, actor=auth.user, principal=auth.principal, lead_id=lead_id, payload=payload, meta=meta
    )
    return await _detail(db, auth, await service.get_lead(db, auth.principal, lead_id))


@router.post("/leads/{lead_id}/convert", response_model=LeadDetail)
async def convert_lead(
    lead_id: uuid.UUID,
    payload: LeadConvert,
    auth: AuthContext = Depends(require_permission("lead.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> LeadDetail:
    lead = await service.convert_lead(
        db, actor=auth.user, principal=auth.principal, lead_id=lead_id, payload=payload, meta=meta
    )
    return await _detail(db, auth, lead)


# --- Pipeline stages ---------------------------------------------------------------


@router.get("/crm/stages", response_model=list[pipeline.StageOut])
async def list_stages(
    auth: AuthContext = Depends(require_permission("lead.read")),
    db: AsyncSession = Depends(get_db),
) -> list[pipeline.StageOut]:
    stages = await pipeline.ensure_stages(db, auth.user.company_id)
    await db.commit()
    return [pipeline.StageOut.model_validate(s) for s in stages]


@router.post("/crm/stages", response_model=pipeline.StageOut, status_code=201)
async def create_stage(
    payload: pipeline.StageCreate,
    auth: AuthContext = Depends(require_permission("lead.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> pipeline.StageOut:
    return pipeline.StageOut.model_validate(
        await pipeline.create_stage(db, auth.user, payload, meta)
    )


@router.patch("/crm/stages/{stage_id}", response_model=pipeline.StageOut)
async def update_stage(
    stage_id: uuid.UUID,
    payload: pipeline.StageUpdate,
    auth: AuthContext = Depends(require_permission("lead.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> pipeline.StageOut:
    return pipeline.StageOut.model_validate(
        await pipeline.update_stage(db, auth.user, stage_id, payload, meta)
    )


@router.delete("/crm/stages/{stage_id}", status_code=204)
async def delete_stage(
    stage_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("lead.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await pipeline.delete_stage(db, auth.user, stage_id, meta)
    return Response(status_code=204)


# --- Customers ---------------------------------------------------------------------


@router.get("/customers", response_model=Page[CustomerSummary])
async def list_customers(
    q: str | None = Query(None, max_length=100),
    customer_status: str | None = Query(None, alias="status", max_length=20),
    product_id: uuid.UUID | None = None,
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("customer.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[CustomerSummary]:
    rows, total = await customer_service.list_customers(
        db,
        auth.principal,
        q=q,
        status=customer_status,
        product_id=product_id,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=await customer_service.summaries(db, rows),
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/customers", response_model=CustomerDetail, status_code=201)
async def create_customer(
    payload: CustomerIn,
    auth: AuthContext = Depends(require_permission("customer.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CustomerDetail:
    customer = await customer_service.create_customer(db, auth.user, auth.principal, payload, meta)
    return await customer_service.detail(db, auth.principal, customer)


@router.get("/customers/export.csv")
async def export_customers(
    auth: AuthContext = Depends(require_permission("customer.export")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    rows, _ = await customer_service.list_customers(
        db, auth.principal, q=None, status=None, product_id=None, limit=10_000, offset=0
    )
    summaries = await customer_service.summaries(db, rows)
    await record_export(db, auth, "customers", len(rows), meta)
    return csv_response(
        "customers.csv",
        [
            "Name",
            "Status",
            "Industry",
            "Email",
            "Phone",
            "Account manager",
            "Products",
            "Next renewal",
        ],
        [
            [
                s.name,
                s.status,
                s.industry,
                s.email,
                s.phone,
                s.account_manager.name if s.account_manager else "",
                "; ".join(p.name for p in s.products),
                s.next_renewal,
            ]
            for s in summaries
        ],
    )


@router.get("/customers/{customer_id}", response_model=CustomerDetail)
async def get_customer(
    customer_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("customer.read")),
    db: AsyncSession = Depends(get_db),
) -> CustomerDetail:
    customer = await customer_service.get_customer(db, auth.principal, customer_id)
    return await customer_service.detail(db, auth.principal, customer)


@router.patch("/customers/{customer_id}", response_model=CustomerDetail)
async def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerPatch,
    auth: AuthContext = Depends(require_permission("customer.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CustomerDetail:
    customer = await customer_service.update_customer(
        db, auth.user, auth.principal, customer_id, payload, meta
    )
    return await customer_service.detail(db, auth.principal, customer)


async def _reload(db: AsyncSession, auth: AuthContext, customer_id: uuid.UUID) -> CustomerDetail:
    customer = await customer_service.get_customer(db, auth.principal, customer_id)
    return await customer_service.detail(db, auth.principal, customer)


@router.post("/customers/{customer_id}/contacts", response_model=CustomerDetail, status_code=201)
async def add_contact(
    customer_id: uuid.UUID,
    payload: ContactIn,
    auth: AuthContext = Depends(require_permission("customer.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CustomerDetail:
    await customer_service.add_contact(db, auth.user, auth.principal, customer_id, payload, meta)
    return await _reload(db, auth, customer_id)


@router.delete("/customers/{customer_id}/contacts/{contact_id}", response_model=CustomerDetail)
async def remove_contact(
    customer_id: uuid.UUID,
    contact_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("customer.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CustomerDetail:
    await customer_service.remove_contact(
        db, auth.user, auth.principal, customer_id, contact_id, meta
    )
    return await _reload(db, auth, customer_id)


@router.put("/customers/{customer_id}/subscriptions", response_model=CustomerDetail)
async def set_subscription(
    customer_id: uuid.UUID,
    payload: SubscriptionIn,
    auth: AuthContext = Depends(require_permission("customer.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CustomerDetail:
    await customer_service.upsert_subscription(
        db, auth.user, auth.principal, customer_id, payload, meta
    )
    return await _reload(db, auth, customer_id)


@router.delete(
    "/customers/{customer_id}/subscriptions/{subscription_id}", response_model=CustomerDetail
)
async def remove_subscription(
    customer_id: uuid.UUID,
    subscription_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("customer.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CustomerDetail:
    await customer_service.remove_subscription(
        db, auth.user, auth.principal, customer_id, subscription_id, meta
    )
    return await _reload(db, auth, customer_id)


@router.post("/customers/{customer_id}/activities", response_model=CustomerDetail, status_code=201)
async def add_customer_activity(
    customer_id: uuid.UUID,
    payload: ActivityIn,
    auth: AuthContext = Depends(require_permission("customer.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> CustomerDetail:
    customer = await customer_service.get_customer(
        db, auth.principal, customer_id, "customer.update"
    )
    await customer_service.log_activity(
        db, auth.user, company_id=auth.user.company_id, payload=payload, customer_id=customer.id
    )
    await db.commit()
    return await _reload(db, auth, customer_id)
