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
    converted_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    converted_at: Mapped[datetime | None]


class PipelineStage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configurable sales pipeline. ``key`` is stored on leads as their status."""

    __tablename__ = "pipeline_stages"
    __table_args__ = (UniqueConstraint("company_id", "key"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    key: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(60))
    position: Mapped[int] = mapped_column(default=0)
    is_won: Mapped[bool] = mapped_column(Boolean, default=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, default=False)


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('prospect', 'active', 'paused', 'churned')", name="status_valid"
        ),
        Index("ix_customers_company_id_name", "company_id", "name"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="active")
    account_manager_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contacts"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    job_title: Mapped[str | None] = mapped_column(String(120))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class CustomerProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A customer's subscription to (or use of) an Eranova product."""

    __tablename__ = "customer_products"
    __table_args__ = (
        UniqueConstraint("customer_id", "product_id"),
        CheckConstraint(
            "status IN ('trial', 'active', 'cancelled', 'expired')", name="status_valid"
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    plan_name: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="active")
    start_date: Mapped[date | None] = mapped_column(Date)
    renewal_date: Mapped[date | None] = mapped_column(Date)


class Activity(UUIDPrimaryKeyMixin, Base):
    """Communication history on a lead or customer. Never edited, so history stays intact."""

    __tablename__ = "crm_activities"
    __table_args__ = (
        CheckConstraint(
            "type IN ('call', 'email', 'meeting', 'note', 'whatsapp', 'sms')", name="type_valid"
        ),
        CheckConstraint("lead_id IS NOT NULL OR customer_id IS NOT NULL", name="has_subject"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(default=utc_now)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())


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
