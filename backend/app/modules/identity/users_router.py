import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.api.pagination import Page, PageParams, page_params
from app.core.errors import NotFoundError
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.authorization import service as authz_service
from app.modules.authorization.policy import ResourceContext, is_allowed
from app.modules.authorization.schemas import RoleAssignmentCreate, RoleAssignmentOut
from app.modules.identity.models import User
from app.modules.identity.schemas import UserSummary

router = APIRouter(prefix="/users", tags=["users"])


class UserDetail(UserSummary):
    roles: list[RoleAssignmentOut]


def _assignment_out(view: authz_service.AssignmentView) -> RoleAssignmentOut:
    a = view.assignment
    return RoleAssignmentOut(
        id=a.id,
        role_id=view.role.id,
        role_slug=view.role.slug,
        role_name=view.role.name,
        scope_type=a.scope_type,
        scope_id=a.scope_id,
        granted_by_user_id=a.granted_by_user_id,
        created_at=a.created_at,
    )


def _user_context(user: User) -> ResourceContext:
    return ResourceContext(company_id=user.company_id, owner_user_id=user.id)


@router.get("", response_model=Page[UserSummary])
async def list_users(
    q: str | None = Query(None, max_length=100),
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("user.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[UserSummary]:
    conditions = [User.company_id == auth.user.company_id]
    company_wide = is_allowed(
        auth.principal, "user.read", ResourceContext(company_id=auth.user.company_id)
    )
    if not company_wide:
        # Department-scoped user access arrives with the people module.
        conditions.append(User.id == auth.user.id)
    if q:
        escaped = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(
                User.email.like(pattern, escape="\\"),
                func.lower(User.full_name).like(pattern, escape="\\"),
            )
        )

    total = await db.scalar(select(func.count()).select_from(User).where(*conditions))
    users = await db.scalars(
        select(User)
        .where(*conditions)
        .order_by(User.full_name)
        .limit(page.limit)
        .offset(page.offset)
    )
    return Page(
        items=[UserSummary.model_validate(u) for u in users],
        total=total or 0,
        limit=page.limit,
        offset=page.offset,
    )


async def _get_visible_user(db: AsyncSession, auth: AuthContext, user_id: uuid.UUID) -> User:
    user = await db.scalar(
        select(User).where(User.id == user_id, User.company_id == auth.user.company_id)
    )
    # Unauthorized and missing records look identical to avoid confirming existence.
    if user is None or not is_allowed(auth.principal, "user.read", _user_context(user)):
        raise NotFoundError("User not found.")
    return user


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("user.read")),
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    user = await _get_visible_user(db, auth, user_id)
    assignments = await authz_service.list_user_assignments(db, user.id)
    return UserDetail(
        **UserSummary.model_validate(user).model_dump(),
        roles=[_assignment_out(a) for a in assignments],
    )


@router.post(
    "/{user_id}/roles", response_model=RoleAssignmentOut, status_code=status.HTTP_201_CREATED
)
async def assign_role(
    user_id: uuid.UUID,
    payload: RoleAssignmentCreate,
    auth: AuthContext = Depends(require_permission("role.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> RoleAssignmentOut:
    view = await authz_service.assign_role(
        db,
        actor=auth.user,
        principal=auth.principal,
        target_user_id=user_id,
        role_id=payload.role_id,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        meta=meta,
    )
    return _assignment_out(view)


@router.delete("/{user_id}/roles/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_role(
    user_id: uuid.UUID,
    assignment_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("role.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await authz_service.revoke_role(
        db,
        actor=auth.user,
        principal=auth.principal,
        target_user_id=user_id,
        assignment_id=assignment_id,
        meta=meta,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
