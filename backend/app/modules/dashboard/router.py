import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context
from app.db.session import get_db
from app.modules.dashboard import service

router = APIRouter(tags=["dashboard"])


class ActivityOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    outcome: str
    actor_type: str
    resource_type: str | None


class SummaryOut(BaseModel):
    generated_at: datetime
    source: str = "Orbit database (live)"
    products: dict | None
    people: dict | None
    accounts: dict | None
    recent_activity: list[ActivityOut] | None


class SearchResultOut(BaseModel):
    type: str
    id: str
    title: str
    subtitle: str | None
    url: str


class SearchOut(BaseModel):
    query: str
    results: list[SearchResultOut]


@router.get("/dashboard/summary", response_model=SummaryOut)
async def dashboard_summary(
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> SummaryOut:
    summary = await service.build_summary(db, auth.principal)
    return SummaryOut(
        generated_at=summary.generated_at,
        products=summary.products,
        people=summary.people,
        accounts=summary.accounts,
        recent_activity=[
            ActivityOut(
                id=e.id,
                created_at=e.created_at,
                action=e.action,
                outcome=e.outcome,
                actor_type=e.actor_type,
                resource_type=e.resource_type,
            )
            for e in summary.recent_activity
        ]
        if summary.recent_activity is not None
        else None,
    )


@router.get("/search", response_model=SearchOut)
async def global_search(
    q: str = Query(..., max_length=100),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> SearchOut:
    found = await service.search(db, auth.principal, q)
    return SearchOut(
        query=found.query, results=[SearchResultOut(**r.__dict__) for r in found.results]
    )
