import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context
from app.db.session import get_db
from app.modules.notifications import service

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int


@router.get("", response_model=NotificationPage)
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> NotificationPage:
    rows, total, unread = await service.list_for(
        db, auth.user.id, unread_only=unread_only, limit=limit, offset=offset
    )
    return NotificationPage(
        items=[NotificationOut.model_validate(r) for r in rows], total=total, unread=unread
    )


@router.post("/read-all", status_code=204)
async def read_all(
    auth: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)
) -> Response:
    await service.mark_read(db, auth.user.id)
    return Response(status_code=204)


@router.post("/{notification_id}/read", status_code=204)
async def read_one(
    notification_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await service.mark_read(db, auth.user.id, notification_id)
    return Response(status_code=204)
