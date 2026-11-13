import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
)

from app.modules.products.models import LifecycleStatus

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
Slug = Annotated[str, StringConstraints(pattern=SLUG_PATTERN, min_length=2, max_length=64)]


_http_url = TypeAdapter(HttpUrl)


def _validate_web_url(value: str) -> str:
    """Only http(s) URLs; rejects javascript:, data: and other schemes."""
    return str(_http_url.validate_python(value))


WebUrl = Annotated[str, StringConstraints(max_length=500), AfterValidator(_validate_web_url)]
AnalyticsSource = Literal["ga4", "search_console", "orbit_sdk", "other"]


class PricingPlan(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    interval: Literal["one_time", "monthly", "quarterly", "yearly", "custom"] | None = None
    notes: str | None = Field(default=None, max_length=300)


class ProductFeature(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)


class ProductFields(BaseModel):
    category: str | None = Field(default=None, max_length=60)
    tagline: str | None = Field(default=None, max_length=200)
    description: str = Field(default="", max_length=10_000)
    details_confirmed: bool = False
    owner_user_id: uuid.UUID | None = None
    logo_url: WebUrl | None = None
    website_url: WebUrl | None = None
    repository_url: WebUrl | None = None
    deployment_ref: str | None = Field(default=None, max_length=200)
    docs_url: WebUrl | None = None
    status_page_url: WebUrl | None = None
    support_email: EmailStr | None = None
    analytics_source: AnalyticsSource | None = None
    analytics_property_id: str | None = Field(default=None, max_length=120)
    launch_date: date | None = None
    pricing: list[PricingPlan] = Field(default_factory=list, max_length=20)
    features: list[ProductFeature] = Field(default_factory=list, max_length=20)


class ProductCreate(ProductFields):
    name: str = Field(min_length=2, max_length=120)
    slug: Slug
    lifecycle_status: LifecycleStatus = LifecycleStatus.DRAFT


class ProductUpdate(BaseModel):
    """Partial update; only provided fields change. Status changes use their own endpoint."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: Slug | None = None
    category: str | None = Field(default=None, max_length=60)
    tagline: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    details_confirmed: bool | None = None
    owner_user_id: uuid.UUID | None = None
    logo_url: WebUrl | None = None
    website_url: WebUrl | None = None
    repository_url: WebUrl | None = None
    deployment_ref: str | None = Field(default=None, max_length=200)
    docs_url: WebUrl | None = None
    status_page_url: WebUrl | None = None
    support_email: EmailStr | None = None
    analytics_source: AnalyticsSource | None = None
    analytics_property_id: str | None = Field(default=None, max_length=120)
    launch_date: date | None = None
    pricing: list[PricingPlan] | None = Field(default=None, max_length=20)
    features: list[ProductFeature] | None = Field(default=None, max_length=20)


class StatusChange(BaseModel):
    status: LifecycleStatus
    reason: str | None = Field(default=None, max_length=500)


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class ProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    category: str | None
    tagline: str | None
    lifecycle_status: str
    details_confirmed: bool
    website_url: str | None
    logo_url: str | None
    is_published: bool
    owner: UserRef | None = None
    updated_at: datetime


class ProductDetail(ProductSummary):
    description: str
    repository_url: str | None
    deployment_ref: str | None
    docs_url: str | None
    status_page_url: str | None
    support_email: str | None
    analytics_source: str | None
    analytics_property_id: str | None
    launch_date: date | None
    pricing: list[dict]
    features: list[dict]
    published_at: datetime | None
    is_public: bool = False
    created_at: datetime
    can_update: bool = False
    can_manage: bool = False
    can_publish: bool = False


class PublicProduct(BaseModel):
    """Marketplace view: only fields safe and intended for the public."""

    name: str
    slug: str
    category: str | None
    tagline: str | None
    description: str
    lifecycle_status: str
    logo_url: str | None
    website_url: str | None
    docs_url: str | None
    status_page_url: str | None
    support_email: str | None
    features: list[dict]
    pricing: list[dict]


class MemberAdd(BaseModel):
    user_id: uuid.UUID
    team_role: str = Field(default="Member", min_length=1, max_length=60)


class MemberOut(BaseModel):
    id: uuid.UUID
    user: UserRef
    team_role: str
    created_at: datetime


class StatusHistoryOut(BaseModel):
    id: uuid.UUID
    from_status: str | None
    to_status: str
    reason: str | None
    changed_by: UserRef | None
    created_at: datetime
