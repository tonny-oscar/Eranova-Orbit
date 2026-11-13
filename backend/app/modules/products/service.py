import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.request_meta import RequestMeta
from app.db.base import utc_now
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import (
    Principal,
    ResourceContext,
    ScopeFilter,
    is_allowed,
    scope_filter,
)
from app.modules.identity.models import User, UserStatus
from app.modules.products.models import (
    PUBLIC_STATUSES,
    LifecycleStatus,
    Product,
    ProductMember,
    ProductStatusHistory,
)
from app.modules.products.schemas import ProductCreate, ProductUpdate

# Fields whose changes are recorded in the audit trail with old and new values.
_AUDITED_FIELDS = {
    "name",
    "slug",
    "owner_user_id",
    "details_confirmed",
    "website_url",
    "repository_url",
    "deployment_ref",
    "support_email",
    "analytics_source",
    "analytics_property_id",
    "launch_date",
}


def product_context(product: Product) -> ResourceContext:
    return ResourceContext(
        company_id=product.company_id,
        product_ids=frozenset({product.id}),
        owner_user_id=product.owner_user_id,
    )


def product_scope_condition(scope: ScopeFilter, user_id: uuid.UUID) -> ColumnElement[bool]:
    if scope.company_wide:
        return Product.id.is_not(None)
    conditions: list[ColumnElement[bool]] = []
    if scope.product_ids:
        conditions.append(Product.id.in_(scope.product_ids))
    if scope.own:
        conditions.append(Product.owner_user_id == user_id)
    return or_(*conditions) if conditions else false()


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass
class ProductPage:
    items: list[Product]
    total: int


async def list_products(
    session: AsyncSession,
    principal: Principal,
    *,
    q: str | None,
    status: LifecycleStatus | None,
    limit: int,
    offset: int,
) -> ProductPage:
    conditions = [
        Product.company_id == principal.company_id,
        product_scope_condition(scope_filter(principal, "product.read"), principal.user_id),
    ]
    if status:
        conditions.append(Product.lifecycle_status == status)
    if q and q.strip():
        pattern = f"%{escape_like(q.strip().lower())}%"
        conditions.append(
            or_(
                func.lower(Product.name).like(pattern, escape="\\"),
                Product.slug.like(pattern, escape="\\"),
                func.lower(func.coalesce(Product.category, "")).like(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(Product).where(*conditions))
    rows = await session.scalars(
        select(Product).where(*conditions).order_by(Product.name).limit(limit).offset(offset)
    )
    return ProductPage(items=list(rows), total=total or 0)


async def get_product_for(
    session: AsyncSession, principal: Principal, product_id: uuid.UUID, permission: str
) -> Product:
    product = await session.scalar(
        select(Product).where(Product.id == product_id, Product.company_id == principal.company_id)
    )
    if product is None or not is_allowed(principal, "product.read", product_context(product)):
        raise NotFoundError("Product not found.")
    if permission != "product.read" and not is_allowed(
        principal, permission, product_context(product)
    ):
        raise PermissionDeniedError("You do not have permission to change this product.")
    return product


async def _ensure_active_user(session: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID):
    user = await session.scalar(
        select(User).where(User.id == user_id, User.company_id == company_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise AppError("The selected user does not exist or is not active.", code="invalid_user")
    return user


async def _ensure_unique(
    session: AsyncSession,
    company_id: uuid.UUID,
    *,
    name: str | None,
    slug: str | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    checks = []
    if name:
        checks.append(("name", func.lower(Product.name) == name.lower()))
    if slug:
        checks.append(("slug", Product.slug == slug))
    for field, condition in checks:
        query = select(Product.id).where(Product.company_id == company_id, condition)
        if exclude_id:
            query = query.where(Product.id != exclude_id)
        if await session.scalar(query):
            raise ConflictError(
                f"Another product already uses this {field}.",
                code=f"product_{field}_taken",
                details=[{"field": field, "message": f"This {field} is already in use."}],
            )


async def create_product(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    payload: ProductCreate,
    meta: RequestMeta,
) -> Product:
    if not is_allowed(principal, "product.create", ResourceContext(company_id=actor.company_id)):
        raise PermissionDeniedError("Registering products requires company-wide access.")
    data = payload.model_dump()
    data["pricing"] = [plan.model_dump(mode="json") for plan in payload.pricing]
    data["features"] = [feature.model_dump(mode="json") for feature in payload.features]
    data["name"] = data["name"].strip()
    await _ensure_unique(session, actor.company_id, name=data["name"], slug=data["slug"])
    if payload.owner_user_id:
        await _ensure_active_user(session, actor.company_id, payload.owner_user_id)

    product = Product(company_id=actor.company_id, created_by_user_id=actor.id, **data)
    session.add(product)
    await session.flush()
    session.add(
        ProductStatusHistory(
            product_id=product.id,
            from_status=None,
            to_status=product.lifecycle_status,
            reason="Registered",
            changed_by_user_id=actor.id,
        )
    )
    await record_event(
        session,
        action="product.create",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="product",
        resource_id=product.id,
        meta=meta,
        details={"name": product.name, "slug": product.slug, "status": product.lifecycle_status},
    )
    await session.commit()
    await session.refresh(product)
    return product


async def update_product(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    product_id: uuid.UUID,
    payload: ProductUpdate,
    meta: RequestMeta,
) -> Product:
    product = await get_product_for(session, principal, product_id, "product.update")
    changes = payload.model_dump(exclude_unset=True)
    if payload.pricing is not None and "pricing" in changes:
        changes["pricing"] = [plan.model_dump(mode="json") for plan in payload.pricing]
    if payload.features is not None and "features" in changes:
        changes["features"] = [feature.model_dump(mode="json") for feature in payload.features]
    if changes.get("owner_user_id"):
        await _ensure_active_user(session, actor.company_id, changes["owner_user_id"])
    if changes.get("name"):
        changes["name"] = changes["name"].strip()
    for required in ("name", "slug", "description", "details_confirmed", "pricing", "features"):
        if required in changes and changes[required] is None:
            raise AppError(f"'{required}' cannot be empty.", code="invalid_field")
    await _ensure_unique(
        session,
        actor.company_id,
        name=changes.get("name"),
        slug=changes.get("slug"),
        exclude_id=product.id,
    )

    audited: dict[str, dict[str, object]] = {}
    for field, value in changes.items():
        old = getattr(product, field)
        if old == value:
            continue
        if field in _AUDITED_FIELDS:
            audited[field] = {"from": _jsonable(old), "to": _jsonable(value)}
        setattr(product, field, value)

    if session.is_modified(product):
        await record_event(
            session,
            action="product.update",
            outcome=AuditOutcome.SUCCESS,
            actor_user_id=actor.id,
            company_id=actor.company_id,
            resource_type="product",
            resource_id=product.id,
            meta=meta,
            details={"changed_fields": sorted(changes), "changes": audited},
        )
        await session.commit()
        await session.refresh(product)
    return product


def _jsonable(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[union-attr]
    return value


async def change_status(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    product_id: uuid.UUID,
    status: LifecycleStatus,
    reason: str | None,
    meta: RequestMeta,
) -> Product:
    product = await get_product_for(session, principal, product_id, "product.update")
    if product.lifecycle_status == status:
        raise AppError("The product already has this status.", code="status_unchanged")
    previous = product.lifecycle_status
    product.lifecycle_status = status
    session.add(
        ProductStatusHistory(
            product_id=product.id,
            from_status=previous,
            to_status=status,
            reason=reason,
            changed_by_user_id=actor.id,
        )
    )
    await record_event(
        session,
        action="product.status.change",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="product",
        resource_id=product.id,
        meta=meta,
        details={"from": previous, "to": status, "reason": reason},
    )
    await session.commit()
    await session.refresh(product)
    return product


async def list_status_history(session: AsyncSession, product_id: uuid.UUID):
    rows = await session.execute(
        select(ProductStatusHistory, User)
        .outerjoin(User, User.id == ProductStatusHistory.changed_by_user_id)
        .where(ProductStatusHistory.product_id == product_id)
        .order_by(ProductStatusHistory.created_at.desc(), ProductStatusHistory.id.desc())
    )
    return list(rows)


async def list_members(session: AsyncSession, product_id: uuid.UUID):
    rows = await session.execute(
        select(ProductMember, User)
        .join(User, User.id == ProductMember.user_id)
        .where(ProductMember.product_id == product_id)
        .order_by(User.full_name)
    )
    return list(rows)


async def add_member(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    product_id: uuid.UUID,
    user_id: uuid.UUID,
    team_role: str,
    meta: RequestMeta,
) -> tuple[ProductMember, User]:
    product = await get_product_for(session, principal, product_id, "product.manage")
    user = await _ensure_active_user(session, actor.company_id, user_id)
    existing = await session.scalar(
        select(ProductMember.id).where(
            ProductMember.product_id == product.id, ProductMember.user_id == user.id
        )
    )
    if existing:
        raise ConflictError("This person is already on the product team.", code="duplicate_member")
    member = ProductMember(
        product_id=product.id,
        user_id=user.id,
        team_role=team_role.strip(),
        added_by_user_id=actor.id,
    )
    session.add(member)
    await session.flush()
    await record_event(
        session,
        action="product.member.add",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="product",
        resource_id=product.id,
        meta=meta,
        details={"user_id": str(user.id), "team_role": member.team_role},
    )
    await session.commit()
    await session.refresh(member)
    return member, user


async def remove_member(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    product_id: uuid.UUID,
    member_id: uuid.UUID,
    meta: RequestMeta,
) -> None:
    product = await get_product_for(session, principal, product_id, "product.manage")
    member = await session.scalar(
        select(ProductMember).where(
            ProductMember.id == member_id, ProductMember.product_id == product.id
        )
    )
    if member is None:
        raise NotFoundError("Team member not found.")
    await session.delete(member)
    await record_event(
        session,
        action="product.member.remove",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="product",
        resource_id=product.id,
        meta=meta,
        details={"user_id": str(member.user_id)},
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Marketplace publishing
# ---------------------------------------------------------------------------


def is_public(product: Product) -> bool:
    return (
        product.is_published
        and product.details_confirmed
        and product.lifecycle_status in PUBLIC_STATUSES
    )


def public_conditions(company_id: uuid.UUID) -> list[ColumnElement[bool]]:
    return [
        Product.company_id == company_id,
        Product.is_published.is_(True),
        Product.details_confirmed.is_(True),
        Product.lifecycle_status.in_(PUBLIC_STATUSES),
    ]


async def set_published(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    product_id: uuid.UUID,
    published: bool,
    meta: RequestMeta,
) -> Product:
    product = await get_product_for(session, principal, product_id, "product.approve")
    if published:
        problems = []
        if not product.details_confirmed:
            problems.append("Confirm the product details first.")
        if product.lifecycle_status not in PUBLIC_STATUSES:
            problems.append("Only beta, live or maintenance products can be published.")
        if not product.description.strip():
            problems.append("Add a description before publishing.")
        if problems:
            raise AppError(
                "This product is not ready to publish.",
                code="not_publishable",
                details=[{"field": "is_published", "message": p} for p in problems],
            )
    if product.is_published == published:
        return product
    product.is_published = published
    product.published_at = utc_now() if published else None
    await record_event(
        session,
        action="product.publish" if published else "product.unpublish",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="product",
        resource_id=product.id,
        meta=meta,
    )
    await session.commit()
    await session.refresh(product)
    return product


async def list_public_products(
    session: AsyncSession, company_id: uuid.UUID, *, q: str | None, category: str | None
) -> list[Product]:
    conditions = public_conditions(company_id)
    if category:
        conditions.append(func.lower(Product.category) == category.strip().lower())
    if q and q.strip():
        pattern = f"%{escape_like(q.strip().lower())}%"
        conditions.append(
            or_(
                func.lower(Product.name).like(pattern, escape="\\"),
                func.lower(func.coalesce(Product.tagline, "")).like(pattern, escape="\\"),
                func.lower(func.coalesce(Product.category, "")).like(pattern, escape="\\"),
            )
        )
    return list(await session.scalars(select(Product).where(*conditions).order_by(Product.name)))


async def get_public_product(session: AsyncSession, company_id: uuid.UUID, slug: str) -> Product:
    product = await session.scalar(
        select(Product).where(*public_conditions(company_id), Product.slug == slug)
    )
    if product is None:
        raise NotFoundError("Product not found.")
    return product


async def product_exists(
    session: AsyncSession, company_id: uuid.UUID, product_id: uuid.UUID
) -> bool:
    """Scope validator used when assigning product-scoped roles."""
    found = await session.scalar(
        select(Product.id).where(Product.id == product_id, Product.company_id == company_id)
    )
    return found is not None


async def owners_by_id(session: AsyncSession, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not user_ids:
        return {}
    users = await session.scalars(select(User).where(User.id.in_(user_ids)))
    return {u.id: u for u in users}
