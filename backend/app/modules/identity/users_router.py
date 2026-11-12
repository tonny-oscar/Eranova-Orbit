import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, EmailStr, Field
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
from app.modules.company.models import Company
from app.modules.identity import admin_service
from app.modules.identity.models import User, UserStatus
from app.modules.identity.schemas import UserSummary
from app.modules.people.models import EmployeeProfile
from app.modules.people.service import department_member_condition

router = APIRouter(prefix="/users", tags=["users"])


class UserDetail(UserSummary):
    roles: list[RoleAssignmentOut]
    can_update: bool = False
    can_manage: bool = False


class UserListItem(UserSummary):
    role_names: list[str] = []


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "disabled"] | None = None


class TemporaryPasswordOut(BaseModel):
    user: UserSummary
    temporary_password: str


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


def _user_context(user: User, department_id: uuid.UUID | None) -> ResourceContext:
    return ResourceContext(
        company_id=user.company_id, owner_user_id=user.id, department_id=department_id
    )


@router.get("", response_model=Page[UserListItem])
async def list_users(
    q: str | None = Query(None, max_length=100),
    user_status: Literal["active", "invited", "disabled"] | None = Query(None, alias="status"),
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("user.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[UserListItem]:
    conditions = [
        User.company_id == auth.user.company_id,
        or_(
            department_member_condition(auth.principal, "user.read"),
            User.id == auth.user.id,
        ),
    ]
    if user_status:
        conditions.append(User.status == user_status)
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
    users = list(
        await db.scalars(
            select(User)
            .where(*conditions)
            .order_by(User.full_name)
            .limit(page.limit)
            .offset(page.offset)
        )
    )
    role_names = await authz_service.role_names_by_user(db, [u.id for u in users])
    return Page(
        items=[
            UserListItem(**UserSummary.model_validate(u).model_dump(), role_names=role_names[u.id])
            for u in users
        ],
        total=total or 0,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("", response_model=TemporaryPasswordOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    auth: AuthContext = Depends(require_permission("user.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TemporaryPasswordOut:
    company = await db.get(Company, auth.user.company_id)
    created = await admin_service.create_user_by_admin(
        db,
        actor=auth.user,
        principal=auth.principal,
        company=company,
        email=payload.email,
        full_name=payload.full_name,
        meta=meta,
    )
    return TemporaryPasswordOut(
        user=UserSummary.model_validate(created.user),
        temporary_password=created.temporary_password,
    )


async def _get_visible_user(db: AsyncSession, auth: AuthContext, user_id: uuid.UUID) -> User:
    user = await db.scalar(
        select(User).where(User.id == user_id, User.company_id == auth.user.company_id)
    )
    department_id = (
        await db.scalar(
            select(EmployeeProfile.department_id).where(EmployeeProfile.user_id == user_id)
        )
        if user
        else None
    )
    # Unauthorized and missing records look identical to avoid confirming existence.
    if user is None or not is_allowed(
        auth.principal, "user.read", _user_context(user, department_id)
    ):
        raise NotFoundError("User not found.")
    return user


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("user.read")),
    db: AsyncSession = Depends(get_db),
) -> UserDetail:
    user = await _get_visible_user(db, auth, user_id)
    return await _user_detail(db, auth, user)


async def _user_detail(db: AsyncSession, auth: AuthContext, user: User) -> UserDetail:
    assignments = await authz_service.list_user_assignments(db, user.id)
    company = ResourceContext(company_id=auth.user.company_id)
    return UserDetail(
        **UserSummary.model_validate(user).model_dump(),
        roles=[_assignment_out(a) for a in assignments],
        can_update=is_allowed(auth.principal, "user.update", company),
        can_manage=is_allowed(auth.principal, "user.manage", company) and user.id != auth.user.id,
    )


@router.patch("/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    auth: AuthContext = Depends(require_permission("user.read")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> UserDetail:
    await _get_visible_user(db, auth, user_id)
    user = await admin_service.update_user(
        db,
        actor=auth.user,
        principal=auth.principal,
        user_id=user_id,
        full_name=payload.full_name,
        status=UserStatus(payload.status) if payload.status else None,
        meta=meta,
    )
    return await _user_detail(db, auth, user)


@router.post("/{user_id}/reset-password", response_model=TemporaryPasswordOut)
async def reset_password(
    user_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("user.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TemporaryPasswordOut:
    temporary = await admin_service.reset_password_by_admin(
        db, actor=auth.user, principal=auth.principal, user_id=user_id, meta=meta
    )
    user = await _get_visible_user(db, auth, user_id)
    return TemporaryPasswordOut(user=UserSummary.model_validate(user), temporary_password=temporary)


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
