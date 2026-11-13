import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class LeadStatus(StrEnum):
    """Starter pipeline. Phase 3 makes stages configurable per pipeline."""

    NEW = "new"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    DEMO_SCHEDULED = "demo_scheduled"
    NEGOTIATION = "negotiation"
    CONVERTED = "converted"
    LOST = "lost"


class LeadPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EnquiryType(StrEnum):
    CONTACT = "contact"
    DEMO = "demo"


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A prospect, deduplicated per email and product of interest."""

    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("company_id", "email", "product_id", postgresql_nulls_not_distinct=True),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="priority_valid"),
        Index("ix_leads_company_id_status", "company_id", "status"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT")
    )
    full_name: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    source: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default=LeadStatus.NEW)
    priority: Mapped[str] = mapped_column(String(10), default=LeadPriority.MEDIUM)
    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    notes: Mapped[str] = mapped_column(Text, default="")
    next_follow_up: Mapped[date | None] = mapped_column(Date)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    last_enquiry_at: Mapped[datetime | None]


class Enquiry(UUIDPrimaryKeyMixin, Base):
    """One website form submission, kept as part of the lead's history."""

    __tablename__ = "enquiries"
    __table_args__ = (
        CheckConstraint("type IN ('contact', 'demo')", name="type_valid"),
        Index("ix_enquiries_ip_hash_created_at", "ip_hash", "created_at"),
        Index("ix_enquiries_email_created_at", "email", "created_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(320))
    message: Mapped[str] = mapped_column(Text, default="")
    preferred_date: Mapped[date | None] = mapped_column(Date)
    consent_privacy: Mapped[bool] = mapped_column(Boolean)
    consent_marketing: Mapped[bool] = mapped_column(Boolean, default=False)
    privacy_notice_version: Mapped[str] = mapped_column(String(40))
    utm_source: Mapped[str | None] = mapped_column(String(100))
    utm_medium: Mapped[str | None] = mapped_column(String(100))
    utm_campaign: Mapped[str | None] = mapped_column(String(100))
    referrer: Mapped[str | None] = mapped_column(String(500))
    landing_page: Mapped[str | None] = mapped_column(String(500))
    # Salted hash, not the raw IP: enough for abuse throttling, minimal personal data.
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())
