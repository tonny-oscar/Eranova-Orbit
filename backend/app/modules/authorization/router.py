import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.db.session import get_db
from app.modules.authorization import service
from app.modules.authorization.schemas import PermissionOut, RoleOut

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
