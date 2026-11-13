import hashlib
import logging
import uuid
from datetime import timedelta

from sqlalchemy import ColumnElement, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import (
    AppError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
)
from app.core.request_meta import RequestMeta
from app.db.base import utc_now
from app.modules.audit.models import ActorType, AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed, scope_filter
from app.modules.company.service import get_company_by_slug
from app.modules.crm.customers import (
    ensure_not_duplicate,
    find_existing_customer,
    get_customer,
    log_activity,
)
from app.modules.crm.models import Contact, Customer, CustomerProduct, Enquiry, Lead
from app.modules.crm.pipeline import stage_keys, won_stage
from app.modules.crm.schemas import EnquiryIn, LeadConvert, LeadCreate, LeadUpdate
from app.modules.identity.models import User, UserStatus
from app.modules.products.models import Product
from app.modules.products.service import escape_like, public_conditions

logger = logging.getLogger(__name__)

# Bump when the published privacy notice changes so each consent records which text was shown.
PRIVACY_NOTICE_VERSION = "2026-11-draft"
MIN_FORM_MS = 3_000
MAX_PER_IP_PER_10_MIN = 5
MAX_PER_EMAIL_PER_HOUR = 3


def hash_ip(ip: str | None, settings: Settings) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(f"{settings.secret_key}:{ip}".encode()).hexdigest()


async def submit_enquiry(
    session: AsyncSession, settings: Settings, payload: EnquiryIn, meta: RequestMeta
) -> None:
    """Create or update the lead for a website enquiry.

    Suspected bots get the same success response as people so the filter
    cannot be probed, but nothing is stored.
    """
    if payload.website.strip() or payload.elapsed_ms < MIN_FORM_MS:
        logger.info("Enquiry dropped by spam filter", extra={"reason": "honeypot_or_too_fast"})
        return

    company = await get_company_by_slug(session, settings.company_slug)
    if company is None:
        raise AppError("Enquiries are not available right now.", code="not_configured")

    email = payload.email.strip().lower()
    now = utc_now()
    ip_hash = hash_ip(meta.ip_address, settings)
    if ip_hash:
        recent_ip = await session.scalar(
            select(func.count())
            .select_from(Enquiry)
            .where(Enquiry.ip_hash == ip_hash, Enquiry.created_at >= now - timedelta(minutes=10))
        )
        if (recent_ip or 0) >= MAX_PER_IP_PER_10_MIN:
            raise RateLimitedError("Too many enquiries. Please try again later.")
    recent_email = await session.scalar(
        select(func.count())
        .select_from(Enquiry)
        .where(Enquiry.email == email, Enquiry.created_at >= now - timedelta(hours=1))
    )
    if (recent_email or 0) >= MAX_PER_EMAIL_PER_HOUR:
        raise RateLimitedError("Too many enquiries. Please try again later.")

    product_id = None
    if payload.product_slug:
        # Only published products can be referenced; anything else is ignored silently.
        product_id = await session.scalar(
            select(Product.id).where(
                *public_conditions(company.id), Product.slug == payload.product_slug
            )
        )

    lead = await session.scalar(
        select(Lead).where(
            Lead.company_id == company.id,
            Lead.email == email,
            Lead.product_id.is_(None) if product_id is None else Lead.product_id == product_id,
        )
    )
    created = lead is None
    if lead is None:
        lead = Lead(
            company_id=company.id,
            email=email,
            product_id=product_id,
            full_name=payload.full_name.strip(),
            source=f"website_{payload.type}",
            status=next(iter(await stage_keys(session, company.id))),
        )
        session.add(lead)
    lead.full_name = payload.full_name.strip()
    if payload.organization:
        lead.organization = payload.organization.strip()
    if payload.phone:
        lead.phone = payload.phone.strip()
    lead.marketing_consent = payload.consent_marketing
    lead.last_enquiry_at = now
    await session.flush()

    attribution = payload.attribution
    session.add(
        Enquiry(
            company_id=company.id,
            lead_id=lead.id,
            type=payload.type,
            email=email,
            message=payload.message.strip(),
            preferred_date=payload.preferred_date,
            consent_privacy=payload.consent_privacy,
            consent_marketing=payload.consent_marketing,
            privacy_notice_version=PRIVACY_NOTICE_VERSION,
            utm_source=attribution.utm_source,
            utm_medium=attribution.utm_medium,
            utm_campaign=attribution.utm_campaign,
            referrer=attribution.referrer,
            landing_page=attribution.landing_page,
            ip_hash=ip_hash,
        )
    )
    await record_event(
        session,
        action="lead.create" if created else "lead.enquiry.add",
        outcome=AuditOutcome.SUCCESS,
        actor_type=ActorType.ANONYMOUS,
        company_id=company.id,
        resource_type="lead",
        resource_id=lead.id,
        meta=meta,
        details={
            "type": payload.type,
            "source": "website",
            "product_id": str(product_id) if product_id else None,
        },
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Staff lead management
# ---------------------------------------------------------------------------


def lead_context(lead: Lead) -> ResourceContext:
    return ResourceContext(
        company_id=lead.company_id,
        product_ids=frozenset({lead.product_id}) if lead.product_id else frozenset(),
        owner_user_id=lead.owner_user_id,
    )


def _scope_condition(principal: Principal) -> ColumnElement[bool]:
    scope = scope_filter(principal, "lead.read")
    if scope.company_wide:
        return true()
    conditions: list[ColumnElement[bool]] = []
    if scope.product_ids:
        conditions.append(Lead.product_id.in_(scope.product_ids))
    if scope.own:
        conditions.append(Lead.owner_user_id == principal.user_id)
    return or_(*conditions) if conditions else false()


async def list_leads(
    session: AsyncSession,
    principal: Principal,
    *,
    q: str | None,
    status: str | None,
    product_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Lead], int]:
    conditions = [Lead.company_id == principal.company_id, _scope_condition(principal)]
    if status:
        conditions.append(Lead.status == status)
    if product_id:
        conditions.append(Lead.product_id == product_id)
    if q and q.strip():
        pattern = f"%{escape_like(q.strip().lower())}%"
        conditions.append(
            or_(
                func.lower(Lead.full_name).like(pattern, escape="\\"),
                Lead.email.like(pattern, escape="\\"),
                func.lower(func.coalesce(Lead.organization, "")).like(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(Lead).where(*conditions))
    leads = await session.scalars(
        select(Lead)
        .where(*conditions)
        .order_by(func.coalesce(Lead.last_enquiry_at, Lead.created_at).desc(), Lead.id)
        .limit(limit)
        .offset(offset)
    )
    return list(leads), total or 0


async def get_lead(session: AsyncSession, principal: Principal, lead_id: uuid.UUID) -> Lead:
    lead = await session.scalar(
        select(Lead).where(Lead.id == lead_id, Lead.company_id == principal.company_id)
    )
    if lead is None or not is_allowed(principal, "lead.read", lead_context(lead)):
        raise NotFoundError("Lead not found.")
    return lead


async def list_enquiries(session: AsyncSession, lead_id: uuid.UUID) -> list[Enquiry]:
    return list(
        await session.scalars(
            select(Enquiry)
            .where(Enquiry.lead_id == lead_id)
            .order_by(Enquiry.created_at.desc(), Enquiry.id.desc())
        )
    )


async def update_lead(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    meta: RequestMeta,
) -> Lead:
    lead = await get_lead(session, principal, lead_id)
    if not is_allowed(principal, "lead.update", lead_context(lead)):
        raise PermissionDeniedError("You cannot update this lead.")
    changes = payload.model_dump(exclude_unset=True)
    for field in ("status", "priority"):
        if field in changes and changes[field] is None:
            raise AppError(f"'{field}' cannot be empty.", code="invalid_field")
    if "status" in changes and changes["status"] not in await stage_keys(session, actor.company_id):
        raise AppError("Unknown pipeline stage.", code="invalid_stage")
    if changes.get("owner_user_id"):
        owner = await session.scalar(
            select(User).where(
                User.id == changes["owner_user_id"], User.company_id == actor.company_id
            )
        )
        if owner is None or owner.status != UserStatus.ACTIVE:
            raise AppError("The selected owner is not an active user.", code="invalid_owner")

    audited = {}
    for field, value in changes.items():
        if field == "notes" and value is None:
            value = ""
        old = getattr(lead, field)
        if old != value:
            if field != "notes":
                audited[field] = {"from": _jsonable(old), "to": _jsonable(value)}
            setattr(lead, field, value)
    if session.is_modified(lead):
        await record_event(
            session,
            action="lead.update",
            outcome=AuditOutcome.SUCCESS,
            actor_user_id=actor.id,
            company_id=actor.company_id,
            resource_type="lead",
            resource_id=lead.id,
            meta=meta,
            details={"changes": audited, "notes_changed": "notes" in changes},
        )
        await session.commit()
        await session.refresh(lead)
    return lead


async def create_lead(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    payload: LeadCreate,
    meta: RequestMeta,
) -> Lead:
    context = ResourceContext(
        company_id=actor.company_id,
        product_ids=frozenset({payload.product_id}) if payload.product_id else frozenset(),
        owner_user_id=payload.owner_user_id or actor.id,
    )
    if not is_allowed(principal, "lead.create", context):
        raise PermissionDeniedError("You cannot create leads here.")
    email = payload.email.strip().lower()
    duplicate = await session.scalar(
        select(Lead.id).where(
            Lead.company_id == actor.company_id,
            Lead.email == email,
            Lead.product_id.is_(None)
            if payload.product_id is None
            else Lead.product_id == payload.product_id,
        )
    )
    if duplicate:
        raise ConflictError(
            "A lead with this email already exists for this product.",
            code="duplicate_lead",
            details=[{"field": "email", "message": str(duplicate)}],
        )
    if payload.product_id and not await session.scalar(
        select(Product.id).where(
            Product.id == payload.product_id, Product.company_id == actor.company_id
        )
    ):
        raise AppError("Product not found.", code="invalid_product")
    stages = await stage_keys(session, actor.company_id)
    lead = Lead(
        company_id=actor.company_id,
        **payload.model_dump(exclude={"email", "owner_user_id"}),
        email=email,
        owner_user_id=payload.owner_user_id or actor.id,
        status=next(iter(stages)),
    )
    session.add(lead)
    await session.flush()
    await record_event(
        session,
        action="lead.create",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="lead",
        resource_id=lead.id,
        meta=meta,
        details={"source": lead.source},
    )
    await session.commit()
    await session.refresh(lead)
    return lead


async def add_lead_activity(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    lead_id: uuid.UUID,
    payload,
    meta: RequestMeta,
) -> None:
    lead = await get_lead(session, principal, lead_id)
    if not is_allowed(principal, "lead.update", lead_context(lead)):
        raise PermissionDeniedError("You cannot add activity to this lead.")
    activity = await log_activity(
        session, actor, company_id=actor.company_id, payload=payload, lead_id=lead.id
    )
    await record_event(
        session,
        action="lead.activity.add",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="lead",
        resource_id=lead.id,
        meta=meta,
        details={"activity_id": str(activity.id), "type": activity.type},
    )
    await session.commit()


async def convert_lead(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    lead_id: uuid.UUID,
    payload: LeadConvert,
    meta: RequestMeta,
) -> Lead:
    """Turn a lead into a customer. The lead, its enquiries and activities are kept
    and linked to the customer, so no history is lost."""
    lead = await get_lead(session, principal, lead_id)
    if not is_allowed(principal, "lead.update", lead_context(lead)):
        raise PermissionDeniedError("You cannot convert this lead.")
    if lead.converted_customer_id:
        raise ConflictError("This lead has already been converted.", code="already_converted")

    if payload.customer_id:
        customer = await get_customer(session, principal, payload.customer_id, "customer.update")
    else:
        if not is_allowed(
            principal, "customer.create", ResourceContext(company_id=actor.company_id)
        ):
            raise PermissionDeniedError("Creating customers requires company-wide access.")
        name = (payload.customer_name or lead.organization or lead.full_name).strip()
        ensure_not_duplicate(await find_existing_customer(session, actor.company_id, name), name)
        customer = Customer(
            company_id=actor.company_id,
            name=name,
            email=lead.email if not lead.organization else None,
            phone=lead.phone,
            status="active",
            account_manager_user_id=payload.account_manager_user_id or lead.owner_user_id,
            created_by_user_id=actor.id,
        )
        session.add(customer)
        await session.flush()

    session.add(
        Contact(
            customer_id=customer.id,
            full_name=lead.full_name,
            email=lead.email,
            phone=lead.phone,
            is_primary=not await session.scalar(
                select(func.count()).select_from(Contact).where(Contact.customer_id == customer.id)
            ),
        )
    )
    if lead.product_id:
        existing = await session.scalar(
            select(CustomerProduct.id).where(
                CustomerProduct.customer_id == customer.id,
                CustomerProduct.product_id == lead.product_id,
            )
        )
        if not existing:
            session.add(
                CustomerProduct(
                    customer_id=customer.id,
                    product_id=lead.product_id,
                    status="active",
                    start_date=utc_now().date(),
                )
            )
    lead.status = (await won_stage(session, actor.company_id)).key
    lead.converted_customer_id = customer.id
    lead.converted_at = utc_now()
    await record_event(
        session,
        action="lead.convert",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="lead",
        resource_id=lead.id,
        meta=meta,
        details={"customer_id": str(customer.id)},
    )
    await session.commit()
    await session.refresh(lead)
    return lead


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, str | int | bool):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[union-attr]
    return str(value)


async def lookup(session: AsyncSession, model, ids: set[uuid.UUID]) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {row.id: row for row in await session.scalars(select(model).where(model.id.in_(ids)))}
