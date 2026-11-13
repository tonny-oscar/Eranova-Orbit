"""Customers, contacts, product subscriptions and the shared activity log."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import ColumnElement, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.request_meta import RequestMeta
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed, scope_filter
from app.modules.crm.models import Activity, Contact, Customer, CustomerProduct, Lead
from app.modules.identity.models import User, UserStatus
from app.modules.products.models import Product
from app.modules.products.service import escape_like

CustomerStatus = Literal["prospect", "active", "paused", "churned"]
SubscriptionStatus = Literal["trial", "active", "cancelled", "expired"]
ActivityType = Literal["call", "email", "meeting", "note", "whatsapp", "sms"]


# --- Schemas -------------------------------------------------------------------


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class CustomerIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    industry: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    status: CustomerStatus = "active"
    account_manager_user_id: uuid.UUID | None = None
    notes: str = Field(default="", max_length=10_000)


class CustomerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    industry: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    status: CustomerStatus | None = None
    account_manager_user_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=10_000)


class ContactIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=120)
    is_primary: bool = False


class ContactOut(ContactIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str | None = None


class SubscriptionIn(BaseModel):
    product_id: uuid.UUID
    plan_name: str | None = Field(default=None, max_length=80)
    status: SubscriptionStatus = "active"
    start_date: date | None = None
    renewal_date: date | None = None


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    product: Ref
    plan_name: str | None
    status: str
    start_date: date | None
    renewal_date: date | None


class ActivityIn(BaseModel):
    type: ActivityType
    subject: str = Field(min_length=2, max_length=200)
    body: str = Field(default="", max_length=10_000)
    occurred_at: datetime | None = None


class ActivityOut(BaseModel):
    id: uuid.UUID
    type: str
    subject: str
    body: str
    occurred_at: datetime
    lead_id: uuid.UUID | None
    customer_id: uuid.UUID | None
    created_by: Ref | None


class CustomerSummary(BaseModel):
    id: uuid.UUID
    name: str
    industry: str | None
    status: str
    email: str | None
    phone: str | None
    account_manager: Ref | None
    products: list[Ref]
    next_renewal: date | None
    created_at: datetime


class CustomerDetail(CustomerSummary):
    website: str | None
    notes: str
    contacts: list[ContactOut]
    subscriptions: list[SubscriptionOut]
    activities: list[ActivityOut]
    source_leads: list[Ref]
    can_update: bool = False


# --- Access ----------------------------------------------------------------------


async def subscribed_product_ids(session: AsyncSession, customer_id: uuid.UUID) -> frozenset:
    return frozenset(
        await session.scalars(
            select(CustomerProduct.product_id).where(CustomerProduct.customer_id == customer_id)
        )
    )


async def customer_context(session: AsyncSession, customer: Customer) -> ResourceContext:
    return ResourceContext(
        company_id=customer.company_id,
        product_ids=await subscribed_product_ids(session, customer.id),
        owner_user_id=customer.account_manager_user_id,
    )


def scope_condition(principal: Principal, permission: str = "customer.read") -> ColumnElement[bool]:
    scope = scope_filter(principal, permission)
    if scope.company_wide:
        return true()
    conditions: list[ColumnElement[bool]] = []
    if scope.product_ids:
        conditions.append(
            Customer.id.in_(
                select(CustomerProduct.customer_id).where(
                    CustomerProduct.product_id.in_(scope.product_ids)
                )
            )
        )
    if scope.own:
        conditions.append(Customer.account_manager_user_id == principal.user_id)
    return or_(*conditions) if conditions else false()


async def get_customer(
    session: AsyncSession,
    principal: Principal,
    customer_id: uuid.UUID,
    permission: str = "customer.read",
) -> Customer:
    customer = await session.scalar(
        select(Customer).where(
            Customer.id == customer_id, Customer.company_id == principal.company_id
        )
    )
    if customer is None:
        raise NotFoundError("Customer not found.")
    context = await customer_context(session, customer)
    if not is_allowed(principal, "customer.read", context):
        raise NotFoundError("Customer not found.")
    if permission != "customer.read" and not is_allowed(principal, permission, context):
        raise PermissionDeniedError("You cannot change this customer.")
    return customer


async def _check_user(session: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID | None):
    if user_id is None:
        return
    user = await session.scalar(
        select(User).where(User.id == user_id, User.company_id == company_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise AppError("The selected account manager is not an active user.", code="invalid_user")


async def _audit(session, actor: User, action: str, customer_id, meta: RequestMeta, details=None):
    await record_event(
        session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="customer",
        resource_id=customer_id,
        meta=meta,
        details=details or {},
    )


# --- Queries ---------------------------------------------------------------------


async def list_customers(
    session: AsyncSession,
    principal: Principal,
    *,
    q: str | None,
    status: str | None,
    product_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Customer], int]:
    conditions = [Customer.company_id == principal.company_id, scope_condition(principal)]
    if status:
        conditions.append(Customer.status == status)
    if product_id:
        conditions.append(
            Customer.id.in_(
                select(CustomerProduct.customer_id).where(CustomerProduct.product_id == product_id)
            )
        )
    if q and q.strip():
        pattern = f"%{escape_like(q.strip().lower())}%"
        conditions.append(
            or_(
                func.lower(Customer.name).like(pattern, escape="\\"),
                func.lower(func.coalesce(Customer.email, "")).like(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(Customer).where(*conditions))
    rows = await session.scalars(
        select(Customer).where(*conditions).order_by(Customer.name).limit(limit).offset(offset)
    )
    return list(rows), total or 0


async def summaries(session: AsyncSession, customers: list[Customer]) -> list[CustomerSummary]:
    ids = [c.id for c in customers]
    subs: dict[uuid.UUID, list[tuple[CustomerProduct, Product]]] = {i: [] for i in ids}
    if ids:
        for sub, product in await session.execute(
            select(CustomerProduct, Product)
            .join(Product, Product.id == CustomerProduct.product_id)
            .where(CustomerProduct.customer_id.in_(ids))
        ):
            subs[sub.customer_id].append((sub, product))
    managers = {
        u.id: u
        for u in await session.scalars(
            select(User).where(User.id.in_({c.account_manager_user_id for c in customers} - {None}))
        )
    }
    out = []
    for c in customers:
        renewals = [
            s.renewal_date
            for s, _ in subs[c.id]
            if s.renewal_date and s.status in ("trial", "active")
        ]
        manager = managers.get(c.account_manager_user_id)
        out.append(
            CustomerSummary(
                id=c.id,
                name=c.name,
                industry=c.industry,
                status=c.status,
                email=c.email,
                phone=c.phone,
                account_manager=Ref(id=manager.id, name=manager.full_name) if manager else None,
                products=[Ref(id=p.id, name=p.name) for _, p in subs[c.id]],
                next_renewal=min(renewals) if renewals else None,
                created_at=c.created_at,
            )
        )
    return out


async def activities_for(
    session: AsyncSession, *, lead_ids: list[uuid.UUID], customer_id: uuid.UUID | None
) -> list[ActivityOut]:
    conditions = []
    if lead_ids:
        conditions.append(Activity.lead_id.in_(lead_ids))
    if customer_id:
        conditions.append(Activity.customer_id == customer_id)
    if not conditions:
        return []
    rows = await session.execute(
        select(Activity, User)
        .outerjoin(User, User.id == Activity.created_by_user_id)
        .where(or_(*conditions))
        .order_by(Activity.occurred_at.desc(), Activity.created_at.desc())
    )
    return [
        ActivityOut(
            id=a.id,
            type=a.type,
            subject=a.subject,
            body=a.body,
            occurred_at=a.occurred_at,
            lead_id=a.lead_id,
            customer_id=a.customer_id,
            created_by=Ref(id=u.id, name=u.full_name) if u else None,
        )
        for a, u in rows
    ]


async def detail(session: AsyncSession, principal: Principal, customer: Customer) -> CustomerDetail:
    summary = (await summaries(session, [customer]))[0]
    contacts = list(
        await session.scalars(
            select(Contact)
            .where(Contact.customer_id == customer.id)
            .order_by(Contact.is_primary.desc(), Contact.full_name)
        )
    )
    subs = await session.execute(
        select(CustomerProduct, Product)
        .join(Product, Product.id == CustomerProduct.product_id)
        .where(CustomerProduct.customer_id == customer.id)
        .order_by(Product.name)
    )
    leads = list(
        await session.scalars(select(Lead).where(Lead.converted_customer_id == customer.id))
    )
    context = await customer_context(session, customer)
    return CustomerDetail(
        **summary.model_dump(),
        website=customer.website,
        notes=customer.notes,
        contacts=[ContactOut.model_validate(c) for c in contacts],
        subscriptions=[
            SubscriptionOut(
                id=s.id,
                product=Ref(id=p.id, name=p.name),
                plan_name=s.plan_name,
                status=s.status,
                start_date=s.start_date,
                renewal_date=s.renewal_date,
            )
            for s, p in subs
        ],
        activities=await activities_for(
            session, lead_ids=[lead.id for lead in leads], customer_id=customer.id
        ),
        source_leads=[Ref(id=lead.id, name=lead.full_name) for lead in leads],
        can_update=is_allowed(principal, "customer.update", context),
    )


# --- Commands --------------------------------------------------------------------


async def create_customer(
    session: AsyncSession, actor: User, principal: Principal, payload: CustomerIn, meta: RequestMeta
) -> Customer:
    if not is_allowed(principal, "customer.create", ResourceContext(company_id=actor.company_id)):
        raise PermissionDeniedError("Creating customers requires company-wide access.")
    await _check_user(session, actor.company_id, payload.account_manager_user_id)
    customer = Customer(
        company_id=actor.company_id, created_by_user_id=actor.id, **payload.model_dump()
    )
    customer.name = customer.name.strip()
    session.add(customer)
    await session.flush()
    await _audit(session, actor, "customer.create", customer.id, meta, {"name": customer.name})
    await session.commit()
    return customer


async def update_customer(
    session: AsyncSession,
    actor: User,
    principal: Principal,
    customer_id: uuid.UUID,
    payload: CustomerPatch,
    meta: RequestMeta,
) -> Customer:
    customer = await get_customer(session, principal, customer_id, "customer.update")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise AppError("Name cannot be empty.", code="invalid_field")
    if changes.get("account_manager_user_id"):
        await _check_user(session, actor.company_id, changes["account_manager_user_id"])
    for field, value in changes.items():
        if field == "notes" and value is None:
            value = ""
        setattr(customer, field, value)
    await _audit(session, actor, "customer.update", customer.id, meta, {"fields": sorted(changes)})
    await session.commit()
    await session.refresh(customer)
    return customer


async def add_contact(
    session: AsyncSession,
    actor: User,
    principal: Principal,
    customer_id: uuid.UUID,
    payload: ContactIn,
    meta: RequestMeta,
) -> Contact:
    customer = await get_customer(session, principal, customer_id, "customer.update")
    if payload.is_primary:
        for existing in await session.scalars(
            select(Contact).where(Contact.customer_id == customer.id)
        ):
            existing.is_primary = False
    contact = Contact(customer_id=customer.id, **payload.model_dump())
    session.add(contact)
    await session.flush()
    await _audit(session, actor, "customer.contact.add", customer.id, meta)
    await session.commit()
    return contact


async def remove_contact(
    session: AsyncSession,
    actor: User,
    principal: Principal,
    customer_id: uuid.UUID,
    contact_id: uuid.UUID,
    meta: RequestMeta,
) -> None:
    customer = await get_customer(session, principal, customer_id, "customer.update")
    contact = await session.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.customer_id == customer.id)
    )
    if contact is None:
        raise NotFoundError("Contact not found.")
    await session.delete(contact)
    await _audit(session, actor, "customer.contact.remove", customer.id, meta)
    await session.commit()


async def upsert_subscription(
    session: AsyncSession,
    actor: User,
    principal: Principal,
    customer_id: uuid.UUID,
    payload: SubscriptionIn,
    meta: RequestMeta,
) -> None:
    customer = await get_customer(session, principal, customer_id, "customer.update")
    product = await session.scalar(
        select(Product).where(
            Product.id == payload.product_id, Product.company_id == actor.company_id
        )
    )
    if product is None:
        raise AppError("Product not found.", code="invalid_product")
    sub = await session.scalar(
        select(CustomerProduct).where(
            CustomerProduct.customer_id == customer.id, CustomerProduct.product_id == product.id
        )
    )
    if sub is None:
        sub = CustomerProduct(customer_id=customer.id, product_id=product.id)
        session.add(sub)
    for field, value in payload.model_dump(exclude={"product_id"}).items():
        setattr(sub, field, value)
    await _audit(
        session,
        actor,
        "customer.subscription.set",
        customer.id,
        meta,
        {"product_id": str(product.id), "status": payload.status},
    )
    await session.commit()


async def remove_subscription(
    session: AsyncSession,
    actor: User,
    principal: Principal,
    customer_id: uuid.UUID,
    subscription_id: uuid.UUID,
    meta: RequestMeta,
) -> None:
    customer = await get_customer(session, principal, customer_id, "customer.update")
    sub = await session.scalar(
        select(CustomerProduct).where(
            CustomerProduct.id == subscription_id, CustomerProduct.customer_id == customer.id
        )
    )
    if sub is None:
        raise NotFoundError("Subscription not found.")
    await session.delete(sub)
    await _audit(session, actor, "customer.subscription.remove", customer.id, meta)
    await session.commit()


async def log_activity(
    session: AsyncSession,
    actor: User,
    *,
    company_id: uuid.UUID,
    payload: ActivityIn,
    lead_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
) -> Activity:
    activity = Activity(
        company_id=company_id,
        lead_id=lead_id,
        customer_id=customer_id,
        type=payload.type,
        subject=payload.subject.strip(),
        body=payload.body.strip(),
        created_by_user_id=actor.id,
    )
    if payload.occurred_at:
        activity.occurred_at = payload.occurred_at
    session.add(activity)
    await session.flush()
    return activity


async def find_existing_customer(
    session: AsyncSession, company_id: uuid.UUID, name: str
) -> Customer | None:
    return await session.scalar(
        select(Customer).where(
            Customer.company_id == company_id, func.lower(Customer.name) == name.strip().lower()
        )
    )


def ensure_not_duplicate(existing: Customer | None, name: str) -> None:
    if existing is not None:
        raise ConflictError(
            f"A customer named '{name}' already exists. Convert into it instead.",
            code="customer_exists",
            details=[{"field": "customer_id", "message": str(existing.id)}],
        )
