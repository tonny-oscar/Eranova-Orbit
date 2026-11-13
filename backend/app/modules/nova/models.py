import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class NovaConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "nova_conversations"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="New conversation")


class NovaMessage(UUIDPrimaryKeyMixin, Base):
    """One turn. Usage fields are filled for assistant messages produced by a model."""

    __tablename__ = "nova_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'tool')", name="role_valid"),
        Index("ix_nova_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_nova_messages_user_created", "user_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nova_conversations.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text, default="")
    via: Mapped[str] = mapped_column(String(10), default="text")
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    tool_call_id: Mapped[str | None] = mapped_column(String(100))
    links: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    created_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())


class NovaToolExecution(UUIDPrimaryKeyMixin, Base):
    """Action history: every tool NOVA tried, with outcome."""

    __tablename__ = "nova_tool_executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('succeeded', 'failed', 'denied', 'invalid', 'pending_approval')",
            name="status_valid",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nova_conversations.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tool: Mapped[str] = mapped_column(String(60))
    authority: Mapped[str] = mapped_column(String(20))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(String(1000), default="")
    error: Mapped[str | None] = mapped_column(String(1000))
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())


class NovaProfile(TimestampMixin, Base):
    """How NOVA should address and answer one person. Owned and editable by them."""

    __tablename__ = "nova_profiles"
    __table_args__ = (
        CheckConstraint(
            "response_style IN ('concise', 'balanced', 'detailed')", name="style_valid"
        ),
        CheckConstraint("language IN ('en', 'sw')", name="language_valid"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    preferred_name: Mapped[str | None] = mapped_column(String(60))
    response_style: Mapped[str] = mapped_column(String(10), default="balanced")
    language: Mapped[str] = mapped_column(String(2), default="en")
    learning_enabled: Mapped[bool] = mapped_column(default=True)


class NovaMemory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Something NOVA remembers about one person. Visible, editable and deletable by them."""

    __tablename__ = "nova_memories"
    __table_args__ = (
        CheckConstraint("source IN ('told', 'learned', 'feedback')", name="source_valid"),
        CheckConstraint(
            "category IN ('preference', 'fact', 'goal', 'style')", name="category_valid"
        ),
        Index("ix_nova_memories_user_active", "user_id", "active"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(20), default="fact")
    source: Mapped[str] = mapped_column(String(10), default="told")
    active: Mapped[bool] = mapped_column(default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None]


class NovaFeedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "nova_feedback"
    __table_args__ = (
        CheckConstraint("rating IN (-1, 1)", name="rating_valid"),
        Index("ix_nova_feedback_message_user", "message_id", "user_id", unique=True),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nova_messages.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())


class NovaApproval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A proposed action awaiting a human decision, bound to exact parameters."""

    __tablename__ = "nova_approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired', 'executed', 'failed')",
            name="status_valid",
        ),
        CheckConstraint("policy IN ('self_confirm', 'second_person')", name="policy_valid"),
        Index("ix_nova_approvals_company_status", "company_id", "status"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT")
    )
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nova_conversations.id", ondelete="SET NULL")
    )
    tool: Mapped[str] = mapped_column(String(60))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB)
    params_hash: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(String(1000))
    policy: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None] = mapped_column(String(500))
    executed_at: Mapped[datetime | None]
    result_summary: Mapped[str | None] = mapped_column(String(1000))
    expires_at: Mapped[datetime]
