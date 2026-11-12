import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    status: str
    last_login_at: datetime | None = None
    must_change_password: bool = False


class CompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    timezone: str


class RoleAssignmentSummary(BaseModel):
    assignment_id: uuid.UUID
    role_id: uuid.UUID
    role_slug: str
    role_name: str
    scope_type: str
    scope_id: uuid.UUID | None


class MeResponse(BaseModel):
    user: UserSummary
    company: CompanySummary
    permissions: list[str]
    roles: list[RoleAssignmentSummary]
    csrf_token: str
    session_expires_at: datetime
