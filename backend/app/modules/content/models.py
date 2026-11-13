import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Pages the public site knows how to render. Adding a page is a code change so
# the site never links to content that has no route.
PAGE_SLUGS: dict[str, str] = {
    "home": "Home",
    "solutions": "Solutions",
    "pricing": "Pricing",
    "resources": "Resources",
    "about": "About",
    "careers": "Careers",
    "contact": "Contact",
    "support": "Support",
    "privacy": "Privacy notice",
}


class ContentPage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Editable public page with a working draft and a separately published copy.

    Text is stored as plain sections and rendered as text, never as HTML.
    """

    __tablename__ = "content_pages"
    __table_args__ = (UniqueConstraint("company_id", "slug"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    slug: Mapped[str] = mapped_column(String(40))

    draft_title: Mapped[str] = mapped_column(String(150), default="")
    draft_summary: Mapped[str] = mapped_column(String(500), default="")
    draft_sections: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    draft_seo_description: Mapped[str] = mapped_column(String(300), default="")

    published_title: Mapped[str | None] = mapped_column(String(150))
    published_summary: Mapped[str | None] = mapped_column(String(500))
    published_sections: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    published_seo_description: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[datetime | None]
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
