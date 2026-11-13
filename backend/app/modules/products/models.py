import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class LifecycleStatus(StrEnum):
    DRAFT = "draft"
    DEVELOPMENT = "development"
    BETA = "beta"
    LIVE = "live"
    MAINTENANCE = "maintenance"
    SUNSET = "sunset"
    RETIRED = "retired"


LIFECYCLE_VALUES = tuple(s.value for s in LifecycleStatus)
PUBLIC_STATUSES = (LifecycleStatus.BETA, LifecycleStatus.LIVE, LifecycleStatus.MAINTENANCE)
_LIFECYCLE_SQL = ", ".join(f"'{v}'" for v in LIFECYCLE_VALUES)


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registered Eranova product.

    Orbit stores registry metadata only. Each product keeps its own
    repository, deployment and database; integrations come through adapters.
    """

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("company_id", "slug"),
        UniqueConstraint("company_id", "name"),
        CheckConstraint(f"lifecycle_status IN ({_LIFECYCLE_SQL})", name="lifecycle_status_valid"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
        Index("ix_products_company_id_lifecycle_status", "company_id", "lifecycle_status"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(60))
    tagline: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    lifecycle_status: Mapped[str] = mapped_column(String(20), default=LifecycleStatus.DRAFT)
    # False until a product owner confirms the public-facing details are accurate.
    details_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    logo_url: Mapped[str | None] = mapped_column(String(500))
    website_url: Mapped[str | None] = mapped_column(String(500))
    repository_url: Mapped[str | None] = mapped_column(String(500))
    deployment_ref: Mapped[str | None] = mapped_column(String(200))
    docs_url: Mapped[str | None] = mapped_column(String(500))
    status_page_url: Mapped[str | None] = mapped_column(String(500))
    support_email: Mapped[str | None] = mapped_column(String(320))
    analytics_source: Mapped[str | None] = mapped_column(String(40))
    analytics_property_id: Mapped[str | None] = mapped_column(String(120))
    launch_date: Mapped[date | None] = mapped_column(Date)
    pricing: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    features: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )

    # Marketplace visibility. A product is public only when published, confirmed
    # and in a public lifecycle status (see PUBLIC_STATUSES).
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    published_at: Mapped[datetime | None]

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class ProductMember(UUIDPrimaryKeyMixin, Base):
    """Team roster for a product. Access rights come from scoped role assignments."""

    __tablename__ = "product_members"
    __table_args__ = (UniqueConstraint("product_id", "user_id"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    team_role: Mapped[str] = mapped_column(String(60), default="Member")
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ProductStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "product_status_history"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(500))
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())
