from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant boundary. Orbit currently runs for Eranova only, but every
    company-owned record carries ``company_id`` so multi-entity support does
    not require a schema rewrite."""

    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Nairobi")
