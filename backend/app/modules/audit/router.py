import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.api.pagination import Page, PageParams, page_params
from app.core.errors import PermissionDeniedError
from app.db.session import get_db
from app.modules.audit import service
from app.modules.authorization.policy import ResourceContext, is_allowed

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    actor_type: str
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    outcome: str
    ip_address: str | None
    correlation_id: str | None
    details: dict[str, Any]


@router.get("", response_model=Page[AuditLogOut])
async def list_audit_logs(
    action: str | None = Query(None, max_length=100),
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = Query(None, max_length=50),
    since: datetime | None = None,
    until: datetime | None = None,
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("audit_log.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[AuditLogOut]:
    # Audit logs span the whole company, so only a company-scoped grant applies.
    if not is_allowed(
        auth.principal, "audit_log.read", ResourceContext(company_id=auth.user.company_id)
    ):
        raise PermissionDeniedError("Audit logs require company-wide access.")
    rows, total = await service.list_events(
        db,
        company_id=auth.user.company_id,
        limit=page.limit,
        offset=page.offset,
        action=action,
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        since=since,
        until=until,
    )
    return Page(
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
