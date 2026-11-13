import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class ReportSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A recurring report. Each run is generated separately for every recipient
    with that recipient's own permissions, so nobody receives data they could
    not open themselves."""

    __tablename__ = "report_schedules"
    __table_args__ = (
        CheckConstraint("frequency IN ('weekly', 'monthly')", name="frequency_valid"),
        CheckConstraint("range_days BETWEEN 1 AND 366", name="range_valid"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    report_key: Mapped[str] = mapped_column(String(40))
    frequency: Mapped[str] = mapped_column(String(10))
    range_days: Mapped[int] = mapped_column(Integer, default=30)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE")
    )
    recipient_user_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime]
    last_run_at: Mapped[datetime | None]


class ReportRun(UUIDPrimaryKeyMixin, Base):
    """A generated report snapshot delivered to one recipient."""

    __tablename__ = "report_runs"
    __table_args__ = (
        Index("ix_report_runs_recipient_generated", "recipient_user_id", "generated_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("report_schedules.id", ondelete="SET NULL"), index=True
    )
    report_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())
