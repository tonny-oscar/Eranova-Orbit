import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

CAMPAIGN_STATUSES = ("planned", "active", "paused", "completed", "cancelled")
CONTENT_KINDS = (
    "social_caption",
    "email",
    "product_description",
    "blog",
    "sales_script",
    "campaign_plan",
    "announcement",
)
CONTENT_STATUSES = ("draft", "in_review", "approved", "scheduled", "published", "failed")
CHANNELS = (
    "facebook",
    "instagram",
    "linkedin",
    "x",
    "tiktok",
    "whatsapp",
    "email",
    "website",
    "blog",
    "sms",
    "events",
    "other",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(_in("status", CAMPAIGN_STATUSES), name="status_valid"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="dates_valid"
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    objective: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(Text, default="")
    channels: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list)
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    budget_currency: Mapped[str | None] = mapped_column(String(3))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class ContentItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A piece of marketing content and its publishing state.

    ``published`` is only ever set from a confirmation: a connected provider's
    success response, or a staff member recording where they published it.
    """

    __tablename__ = "content_items"
    __table_args__ = (
        CheckConstraint(_in("status", CONTENT_STATUSES), name="status_valid"),
        CheckConstraint(_in("kind", CONTENT_KINDS), name="kind_valid"),
        CheckConstraint(
            "status <> 'published' OR (published_at IS NOT NULL AND publish_method IS NOT NULL)",
            name="published_confirmed",
        ),
        Index("ix_content_items_company_schedule", "company_id", "scheduled_for"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(30))
    channel: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    scheduled_for: Mapped[datetime | None]
    published_at: Mapped[datetime | None]
    published_url: Mapped[str | None] = mapped_column(String(500))
    publish_method: Mapped[str | None] = mapped_column(String(20))
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    failure_reason: Mapped[str | None] = mapped_column(String(500))
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None]
    review_note: Mapped[str | None] = mapped_column(String(1000))


class CampaignMetric(UUIDPrimaryKeyMixin, Base):
    """A performance figure for a campaign, always labelled with its source."""

    __tablename__ = "campaign_metrics"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = mapped_column(String(60))
    value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(120))
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())
