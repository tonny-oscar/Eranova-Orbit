import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.authorization.catalogue import ScopeType


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    resource: str
    action: str
    description: str
    is_sensitive: bool


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str
    is_system: bool
    is_locked: bool
    permissions: list[str]
    assignment_count: int


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    permissions: list[str] = Field(default_factory=list, max_length=500)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] | None = Field(default=None, max_length=500)


class RoleAssignmentCreate(BaseModel):
    role_id: uuid.UUID
    scope_type: ScopeType = ScopeType.COMPANY
    scope_id: uuid.UUID | None = None


class RoleAssignmentOut(BaseModel):
    id: uuid.UUID
    role_id: uuid.UUID
    role_slug: str
    role_name: str
    scope_type: str
    scope_id: uuid.UUID | None
    granted_by_user_id: uuid.UUID | None
    created_at: datetime
