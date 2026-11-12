import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.people.models import EmploymentType


class PersonRef(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class DepartmentRef(BaseModel):
    id: uuid.UUID
    name: str


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    head_user_id: uuid.UUID | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    head_user_id: uuid.UUID | None = None


class DepartmentOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    head: PersonRef | None
    member_count: int
    created_at: datetime


class EmployeeUpdate(BaseModel):
    department_id: uuid.UUID | None = None
    job_title: str | None = Field(default=None, max_length=120)
    manager_user_id: uuid.UUID | None = None
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    start_date: date | None = None


class EmployeeOut(BaseModel):
    user: PersonRef
    status: str
    department: DepartmentRef | None
    job_title: str | None
    manager: PersonRef | None
    employment_type: str | None
    start_date: date | None
    has_profile: bool
    can_update: bool = False
