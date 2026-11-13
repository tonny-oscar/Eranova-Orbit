import re
import uuid

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.request_meta import RequestMeta
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.crm.models import Lead, PipelineStage
from app.modules.identity.models import User

# Starter pipeline from the brief; administrators can rename, reorder and extend it.
STARTER_STAGES = [
    ("new", "New", False, False),
    ("contacted", "Contacted", False, False),
    ("interested", "Interested", False, False),
    ("demo_scheduled", "Demo Scheduled", False, False),
    ("negotiation", "Negotiation", False, False),
    ("converted", "Converted", True, False),
    ("lost", "Lost", False, True),
]


class StageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    position: int
    is_won: bool
    is_lost: bool


class StageCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    is_won: bool = False
    is_lost: bool = False


class StageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=60)
    position: int | None = Field(default=None, ge=0, le=100)
    is_won: bool | None = None
    is_lost: bool | None = None


async def ensure_stages(session: AsyncSession, company_id: uuid.UUID) -> list[PipelineStage]:
    stages = list(
        await session.scalars(
            select(PipelineStage)
            .where(PipelineStage.company_id == company_id)
            .order_by(PipelineStage.position, PipelineStage.name)
        )
    )
    if stages:
        return stages
    for position, (key, name, won, lost) in enumerate(STARTER_STAGES):
        session.add(
            PipelineStage(
                company_id=company_id,
                key=key,
                name=name,
                position=position,
                is_won=won,
                is_lost=lost,
            )
        )
    await session.flush()
    return await ensure_stages(session, company_id)


async def stage_keys(session: AsyncSession, company_id: uuid.UUID) -> dict[str, PipelineStage]:
    return {s.key: s for s in await ensure_stages(session, company_id)}


async def won_stage(session: AsyncSession, company_id: uuid.UUID) -> PipelineStage:
    for stage in await ensure_stages(session, company_id):
        if stage.is_won:
            return stage
    raise AppError("Configure a 'won' pipeline stage before converting leads.", code="no_won_stage")


def _audit(session, actor: User, action: str, stage_id, meta: RequestMeta, details: dict):
    return record_event(
        session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="pipeline_stage",
        resource_id=stage_id,
        meta=meta,
        details=details,
    )


async def create_stage(
    session: AsyncSession, actor: User, payload: StageCreate, meta: RequestMeta
) -> PipelineStage:
    stages = await stage_keys(session, actor.company_id)
    base = re.sub(r"[^a-z0-9]+", "_", payload.name.lower()).strip("_")[:28] or "stage"
    key, n = base, 2
    while key in stages:
        key, n = f"{base}_{n}", n + 1
    position = (max((s.position for s in stages.values()), default=-1)) + 1
    stage = PipelineStage(
        company_id=actor.company_id,
        key=key,
        name=payload.name.strip(),
        position=position,
        is_won=payload.is_won,
        is_lost=payload.is_lost,
    )
    session.add(stage)
    await session.flush()
    await _audit(session, actor, "pipeline_stage.create", stage.id, meta, {"name": stage.name})
    await session.commit()
    return stage


async def update_stage(
    session: AsyncSession, actor: User, stage_id: uuid.UUID, payload: StageUpdate, meta: RequestMeta
) -> PipelineStage:
    stage = await session.scalar(
        select(PipelineStage).where(
            PipelineStage.id == stage_id, PipelineStage.company_id == actor.company_id
        )
    )
    if stage is None:
        raise NotFoundError("Stage not found.")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(stage, field, value.strip() if isinstance(value, str) else value)
    if stage.is_won and stage.is_lost:
        raise AppError("A stage cannot be both won and lost.", code="invalid_stage")
    await _audit(
        session, actor, "pipeline_stage.update", stage.id, meta, {"changes": list(changes)}
    )
    await session.commit()
    return stage


async def delete_stage(
    session: AsyncSession, actor: User, stage_id: uuid.UUID, meta: RequestMeta
) -> None:
    stage = await session.scalar(
        select(PipelineStage).where(
            PipelineStage.id == stage_id, PipelineStage.company_id == actor.company_id
        )
    )
    if stage is None:
        raise NotFoundError("Stage not found.")
    in_use = await session.scalar(
        select(func.count())
        .select_from(Lead)
        .where(Lead.company_id == actor.company_id, Lead.status == stage.key)
    )
    if in_use:
        raise ConflictError(
            f"{in_use} lead(s) are in this stage. Move them first.", code="stage_in_use"
        )
    await session.delete(stage)
    await _audit(session, actor, "pipeline_stage.delete", stage_id, meta, {"key": stage.key})
    await session.commit()
