import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_request_meta
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.crm.service import lookup
from app.modules.identity.models import User
from app.modules.nova import service
from app.modules.nova.models import NovaApproval, NovaConversation, NovaMessage, NovaToolExecution
from app.modules.nova.service import DecisionIn, MessageIn

router = APIRouter(prefix="/nova", tags=["nova"])


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime


class ExecutionOut(BaseModel):
    id: uuid.UUID
    tool: str
    authority: str
    status: str
    summary: str
    error: str | None
    approval_id: uuid.UUID | None
    created_at: datetime


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    via: str
    links: list[dict]
    status: str
    provider: str | None
    model: str | None
    created_at: datetime


class ApprovalOut(BaseModel):
    id: uuid.UUID
    tool: str
    summary: str
    arguments: dict
    policy: str
    reason: str
    status: str
    requester: dict | None
    decided_by: dict | None
    decided_at: datetime | None
    decision_note: str | None
    result_summary: str | None
    created_at: datetime
    expires_at: datetime
    can_decide: bool


def _message(m: NovaMessage) -> MessageOut:
    return MessageOut.model_validate(m, from_attributes=True)


def _execution(e: NovaToolExecution) -> ExecutionOut:
    return ExecutionOut.model_validate(e, from_attributes=True)


async def _approvals_out(db, auth: AuthContext, rows: list[NovaApproval]) -> list[ApprovalOut]:
    users = await lookup(
        db, User, {a.requester_user_id for a in rows} | {a.decided_by_user_id for a in rows}
    )

    def ref(uid):
        u = users.get(uid)
        return {"id": str(u.id), "name": u.full_name} if u else None

    return [
        ApprovalOut(
            id=a.id,
            tool=a.tool,
            summary=a.summary,
            arguments=a.arguments,
            policy=a.policy,
            reason=a.reason,
            status=a.status,
            requester=ref(a.requester_user_id),
            decided_by=ref(a.decided_by_user_id),
            decided_at=a.decided_at,
            decision_note=a.decision_note,
            result_summary=a.result_summary,
            created_at=a.created_at,
            expires_at=a.expires_at,
            can_decide=service.can_decide(auth.user, auth.principal, a),
        )
        for a in rows
    ]


@router.get("/status")
async def status(auth: AuthContext = Depends(get_auth_context)) -> dict:
    return service.status_info(auth.principal)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    auth: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)
):
    rows = await db.scalars(
        select(NovaConversation)
        .where(NovaConversation.user_id == auth.user.id)
        .order_by(NovaConversation.updated_at.desc())
        .limit(50)
    )
    return [ConversationOut.model_validate(c, from_attributes=True) for c in rows]


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    auth: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)
):
    convo = NovaConversation(company_id=auth.user.company_id, user_id=auth.user.id)
    db.add(convo)
    await db.commit()
    await db.refresh(convo)
    return ConversationOut.model_validate(convo, from_attributes=True)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    convo = await service.get_conversation(db, auth.user, conversation_id)
    messages = await db.scalars(
        select(NovaMessage)
        .where(NovaMessage.conversation_id == convo.id, NovaMessage.role != "tool")
        .order_by(NovaMessage.created_at)
    )
    executions = await db.scalars(
        select(NovaToolExecution)
        .where(NovaToolExecution.conversation_id == convo.id)
        .order_by(NovaToolExecution.created_at)
    )
    return {
        "conversation": ConversationOut.model_validate(convo, from_attributes=True),
        "messages": [_message(m) for m in messages],
        "executions": [_execution(e) for e in executions],
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    convo = await service.get_conversation(db, auth.user, conversation_id)
    await db.delete(convo)
    await db.commit()
    return Response(status_code=204)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageIn,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> dict:
    reply = await service.send_message(
        db, auth.user, auth.principal, conversation_id, payload, meta
    )
    pending_ids = [e.approval_id for e in reply["executions"] if e.approval_id]
    approvals = []
    if pending_ids:
        rows = list(await db.scalars(select(NovaApproval).where(NovaApproval.id.in_(pending_ids))))
        approvals = await _approvals_out(db, auth, rows)
    return {
        "message": _message(reply["message"]),
        "executions": [_execution(e) for e in reply["executions"]],
        "approvals": approvals,
    }


@router.get("/approvals", response_model=list[ApprovalOut])
async def list_approvals(
    approval_status: str | None = Query(None, alias="status", max_length=20),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.list_approvals(db, auth.user, auth.principal, approval_status)
    out = await _approvals_out(db, auth, rows)
    await db.commit()
    return out


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalOut)
async def decide(
    approval_id: uuid.UUID,
    payload: DecisionIn,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
):
    approval = await service.decide(db, auth.user, auth.principal, approval_id, payload, meta)
    return (await _approvals_out(db, auth, [approval]))[0]


@router.get("/usage")
async def usage(
    days: int = Query(30, ge=1, le=365),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await service.usage(db, auth.user, auth.principal, days)
