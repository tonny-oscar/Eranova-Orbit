import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.authorization import service
from app.modules.authorization.schemas import PermissionOut, RoleCreate, RoleOut, RoleUpdate

router = APIRouter(tags=["authorization"])


def _role_out(view: service.RoleView) -> RoleOut:
    return RoleOut(
        id=view.role.id,
        name=view.role.name,
        slug=view.role.slug,
        description=view.role.description,
        is_system=view.role.is_system,
        is_locked=view.role.is_locked,
        permissions=view.permission_keys,
        assignment_count=view.assignment_count,
    )


@router.get("/authz/permissions", response_model=list[PermissionOut])
async def list_permissions(
    _: AuthContext = Depends(require_permission("role.read")),
    db: AsyncSession = Depends(get_db),
) -> list[PermissionOut]:
    return [PermissionOut.model_validate(p) for p in await service.list_permissions(db)]


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    auth: AuthContext = Depends(require_permission("role.read")),
    db: AsyncSession = Depends(get_db),
) -> list[RoleOut]:
    return [_role_out(v) for v in await service.list_roles(db, auth.user.company_id)]


@router.get("/roles/{role_id}", response_model=RoleOut)
async def get_role(
    role_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("role.read")),
    db: AsyncSession = Depends(get_db),
) -> RoleOut:
    return _role_out(await service.get_role(db, auth.user.company_id, role_id))


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    auth: AuthContext = Depends(require_permission("role.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> RoleOut:
    view = await service.create_role(
        db,
        actor=auth.user,
        principal=auth.principal,
        name=payload.name,
        description=payload.description,
        permission_keys=set(payload.permissions),
        meta=meta,
    )
    return _role_out(view)


@router.patch("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    auth: AuthContext = Depends(require_permission("role.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> RoleOut:
    view = await service.update_role(
        db,
        actor=auth.user,
        principal=auth.principal,
        role_id=role_id,
        name=payload.name,
        description=payload.description,
        permission_keys=set(payload.permissions) if payload.permissions is not None else None,
        meta=meta,
    )
    return _role_out(view)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("role.delete")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.delete_role(
        db, actor=auth.user, principal=auth.principal, role_id=role_id, meta=meta
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
