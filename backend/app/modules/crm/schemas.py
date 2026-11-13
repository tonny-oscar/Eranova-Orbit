import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.crm.models import EnquiryType, LeadPriority


class Attribution(BaseModel):
    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)
    referrer: str | None = Field(default=None, max_length=500)
    landing_page: str | None = Field(default=None, max_length=500)


class EnquiryIn(BaseModel):
    type: EnquiryType
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[0-9+()\-\s]*$")
    organization: str | None = Field(default=None, max_length=200)
    product_slug: str | None = Field(default=None, max_length=64)
    message: str = Field(default="", max_length=3_000)
    preferred_date: date | None = None
    consent_privacy: bool
    consent_marketing: bool = False
    attribution: Attribution = Field(default_factory=Attribution)
    # Spam protection: a hidden field humans leave empty, and time spent on the form.
    website: str = Field(default="", max_length=200)
    elapsed_ms: int = Field(default=0, ge=0)

    @field_validator("consent_privacy")
    @classmethod
    def _consent_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must accept the privacy notice to send an enquiry.")
        return value


class EnquiryAccepted(BaseModel):
    status: str = "received"
    message: str = "Thank you. Our team will get back to you."


class ProductRef(BaseModel):
    id: uuid.UUID
    name: str


class PersonRef(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class LeadSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    organization: str | None
    email: str
    phone: str | None
    product: ProductRef | None
    source: str
    status: str
    priority: str
    owner: PersonRef | None
    next_follow_up: date | None
    last_enquiry_at: datetime | None
    created_at: datetime


class EnquiryOut(BaseModel):
    id: uuid.UUID
    type: str
    message: str
    preferred_date: date | None
    consent_privacy: bool
    consent_marketing: bool
    privacy_notice_version: str
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    referrer: str | None
    landing_page: str | None
    created_at: datetime


class LeadDetail(LeadSummary):
    notes: str
    expected_value: Decimal | None
    currency: str | None
    marketing_consent: bool
    enquiries: list[EnquiryOut]
    activities: list = []
    converted_customer: ProductRef | None = None
    converted_at: datetime | None = None
    can_update: bool = False
    can_convert: bool = False


class LeadCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    organization: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40, pattern=r"^[0-9+()\-\s]*$")
    product_id: uuid.UUID | None = None
    source: str = Field(default="manual", max_length=40)
    priority: LeadPriority = LeadPriority.MEDIUM
    expected_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    notes: str = Field(default="", max_length=10_000)
    next_follow_up: date | None = None
    owner_user_id: uuid.UUID | None = None


class LeadConvert(BaseModel):
    """Convert into an existing customer, or create one named ``customer_name``."""

    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(default=None, min_length=2, max_length=200)
    account_manager_user_id: uuid.UUID | None = None


class LeadUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=30)
    priority: LeadPriority | None = None
    owner_user_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=10_000)
    next_follow_up: date | None = None
    expected_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
