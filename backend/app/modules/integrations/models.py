import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class IntegrationConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A configured connection to an external system.

    Credentials are never stored here: ``secret_ref`` names a server-side
    environment variable (INTEGRATION_*) that holds the actual value.
    """

    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("company_id", "name"),
        CheckConstraint("status IN ('active', 'paused', 'error')", name="status_valid"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    secret_ref: Mapped[str | None] = mapped_column(String(80))
    webhook_secret_ref: Mapped[str | None] = mapped_column(String(80))
    capabilities: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    sync_interval_minutes: Mapped[int] = mapped_column(default=60)
    last_sync_at: Mapped[datetime | None]
    last_success_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class SyncRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "integration_sync_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'success', 'failed')", name="status_valid"),
        Index("ix_integration_sync_runs_connection_started", "connection_id", "started_at"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integration_connections.id", ondelete="CASCADE")
    )
    trigger: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())
    finished_at: Mapped[datetime | None]
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(String(500))


class IntegrationRecord(UUIDPrimaryKeyMixin, Base):
    """Minimal normalised copy of an external fact (deployment, PR, metric snapshot)."""

    __tablename__ = "integration_records"
    __table_args__ = (
        UniqueConstraint("connection_id", "kind", "external_id"),
        Index(
            "ix_integration_records_connection_kind_observed",
            "connection_id",
            "kind",
            "observed_at",
        ),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integration_connections.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    observed_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())


class WebhookEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "integration_webhook_events"
    __table_args__ = (UniqueConstraint("connection_id", "delivery_id"),)

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True
    )
    delivery_id: Mapped[str] = mapped_column(String(120))
    event_type: Mapped[str] = mapped_column(String(60))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    received_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())
