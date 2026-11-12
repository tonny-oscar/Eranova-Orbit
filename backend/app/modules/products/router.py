import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.api.pagination import Page, PageParams, page_params
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.authorization.policy import is_allowed
from app.modules.identity.models import User
from app.modules.products import service
from app.modules.products.models import LifecycleStatus, Product
from app.modules.products.schemas import (
    MemberAdd,
    MemberOut,
    ProductCreate,
    ProductDetail,
    ProductSummary,
    ProductUpdate,
    StatusChange,
    StatusHistoryOut,
    UserRef,
)

router = APIRouter(prefix="/products", tags=["products"])


def _user_ref(user: User | None) -> UserRef | None:
    if user is None:
        return None
    return UserRef(id=user.id, full_name=user.full_name, email=user.email)


async def _detail(db: AsyncSession, auth: AuthContext, product: Product) -> ProductDetail:
    owners = await service.owners_by_id(db, {product.owner_user_id} - {None})
    context = service.product_context(product)
    return ProductDetail.model_validate(
        {
            **{c.key: getattr(product, c.key) for c in Product.__table__.columns},
            "owner": _user_ref(owners.get(product.owner_user_id)),
            "can_update": is_allowed(auth.principal, "product.update", context),
            "can_manage": is_allowed(auth.principal, "product.manage", context),
        }
    )


@router.get("", response_model=Page[ProductSummary])
async def list_products(
    q: str | None = Query(None, max_length=100),
    lifecycle_status: LifecycleStatus | None = Query(None, alias="status"),
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("product.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[ProductSummary]:
    result = await service.list_products(
        db, auth.principal, q=q, status=lifecycle_status, limit=page.limit, offset=page.offset
    )
    owners = await service.owners_by_id(
        db, {p.owner_user_id for p in result.items if p.owner_user_id}
    )
    items = [
        ProductSummary.model_validate(p).model_copy(
            update={"owner": _user_ref(owners.get(p.owner_user_id))}
        )
        for p in result.items
    ]
    return Page(items=items, total=result.total, limit=page.limit, offset=page.offset)


@router.post("", response_model=ProductDetail, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    auth: AuthContext = Depends(require_permission("product.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProductDetail:
    product = await service.create_product(
        db, actor=auth.user, principal=auth.principal, payload=payload, meta=meta
    )
    return await _detail(db, auth, product)


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(
    product_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("product.read")),
    db: AsyncSession = Depends(get_db),
) -> ProductDetail:
    product = await service.get_product_for(db, auth.principal, product_id, "product.read")
    return await _detail(db, auth, product)


@router.patch("/{product_id}", response_model=ProductDetail)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    auth: AuthContext = Depends(require_permission("product.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProductDetail:
    product = await service.update_product(
        db,
        actor=auth.user,
        principal=auth.principal,
        product_id=product_id,
        payload=payload,
        meta=meta,
    )
    return await _detail(db, auth, product)


@router.post("/{product_id}/status", response_model=ProductDetail)
async def change_status(
    product_id: uuid.UUID,
    payload: StatusChange,
    auth: AuthContext = Depends(require_permission("product.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProductDetail:
    product = await service.change_status(
        db,
        actor=auth.user,
        principal=auth.principal,
        product_id=product_id,
        status=payload.status,
        reason=payload.reason,
        meta=meta,
    )
    return await _detail(db, auth, product)


@router.get("/{product_id}/status-history", response_model=list[StatusHistoryOut])
async def status_history(
    product_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("product.read")),
    db: AsyncSession = Depends(get_db),
) -> list[StatusHistoryOut]:
    product = await service.get_product_for(db, auth.principal, product_id, "product.read")
    return [
        StatusHistoryOut(
            id=entry.id,
            from_status=entry.from_status,
            to_status=entry.to_status,
            reason=entry.reason,
            changed_by=_user_ref(user),
            created_at=entry.created_at,
        )
        for entry, user in await service.list_status_history(db, product.id)
    ]


@router.get("/{product_id}/members", response_model=list[MemberOut])
async def list_members(
    product_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("product.read")),
    db: AsyncSession = Depends(get_db),
) -> list[MemberOut]:
    product = await service.get_product_for(db, auth.principal, product_id, "product.read")
    return [
        MemberOut(id=m.id, user=_user_ref(u), team_role=m.team_role, created_at=m.created_at)
        for m, u in await service.list_members(db, product.id)
    ]


@router.post("/{product_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    product_id: uuid.UUID,
    payload: MemberAdd,
    auth: AuthContext = Depends(require_permission("product.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> MemberOut:
    member, user = await service.add_member(
        db,
        actor=auth.user,
        principal=auth.principal,
        product_id=product_id,
        user_id=payload.user_id,
        team_role=payload.team_role,
        meta=meta,
    )
    return MemberOut(
        id=member.id, user=_user_ref(user), team_role=member.team_role, created_at=member.created_at
    )


@router.delete("/{product_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    product_id: uuid.UUID,
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("product.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.remove_member(
        db,
        actor=auth.user,
        principal=auth.principal,
        product_id=product_id,
        member_id=member_id,
        meta=meta,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
