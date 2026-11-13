import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.products.schemas import WebUrl

Priority = Literal["low", "medium", "high", "critical"]
ProjectStatus = Literal["planned", "active", "on_hold", "completed", "cancelled"]
LinkKind = Literal[
    "github_issue", "github_pr", "commit", "deployment", "document", "attachment", "other"
]


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=10_000)
    product_id: uuid.UUID | None = None
    status: ProjectStatus = "planned"
    priority: Priority = "medium"
    manager_user_id: uuid.UUID | None = None
    start_date: date | None = None
    due_date: date | None = None
    budget_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    budget_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    repository_url: WebUrl | None = None
    docs_url: WebUrl | None = None


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=10_000)
    status: ProjectStatus | None = None
    priority: Priority | None = None
    manager_user_id: uuid.UUID | None = None
    start_date: date | None = None
    due_date: date | None = None
    budget_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    budget_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    repository_url: WebUrl | None = None
    docs_url: WebUrl | None = None


class MilestoneIn(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    due_date: date | None = None
    completed: bool = False


class MilestoneOut(BaseModel):
    id: uuid.UUID
    title: str
    due_date: date | None
    completed_at: datetime | None


class MemberIn(BaseModel):
    user_id: uuid.UUID
    role_label: str = Field(default="Member", min_length=1, max_length=60)


class MemberOut(BaseModel):
    id: uuid.UUID
    user: Ref
    role_label: str


class TaskCounts(BaseModel):
    total: int = 0
    open: int = 0
    overdue: int = 0
    awaiting_review: int = 0
    completed: int = 0


class ProjectSummary(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    priority: str
    product: Ref | None
    manager: Ref | None
    start_date: date | None
    due_date: date | None
    tasks: TaskCounts


class ProjectDetail(ProjectSummary):
    description: str
    budget_amount: Decimal | None
    budget_currency: str | None
    repository_url: str | None
    docs_url: str | None
    members: list[MemberOut]
    milestones: list[MilestoneOut]
    can_update: bool = False
    can_create_tasks: bool = False


class TaskIn(BaseModel):
    project_id: uuid.UUID
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=20_000)
    parent_task_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None
    priority: Priority = "medium"
    assignee_user_id: uuid.UUID | None = None
    start_date: date | None = None
    due_date: date | None = None
    estimate_hours: Decimal | None = Field(default=None, ge=0, le=10_000, decimal_places=2)


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=20_000)
    milestone_id: uuid.UUID | None = None
    priority: Priority | None = None
    assignee_user_id: uuid.UUID | None = None
    start_date: date | None = None
    due_date: date | None = None
    estimate_hours: Decimal | None = Field(default=None, ge=0, le=10_000, decimal_places=2)


class TransitionIn(BaseModel):
    to: Literal["in_progress", "submitted", "under_review", "completed", "cancelled"]
    note: str | None = Field(default=None, max_length=2_000)


class ReviewIn(BaseModel):
    decision: Literal["approved", "revision_requested"]
    comment: str = Field(default="", max_length=5_000)


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class DependencyIn(BaseModel):
    depends_on_task_id: uuid.UUID


class LinkIn(BaseModel):
    kind: LinkKind
    url: WebUrl
    title: str | None = Field(default=None, max_length=200)


class TaskSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    priority: str
    project: Ref
    assignee: Ref | None
    due_date: date | None
    parent_task_id: uuid.UUID | None
    is_overdue: bool
    updated_at: datetime


class CommentOut(BaseModel):
    id: uuid.UUID
    author: Ref | None
    body: str
    created_at: datetime


class ReviewOut(BaseModel):
    id: uuid.UUID
    reviewer: Ref | None
    decision: str
    comment: str
    created_at: datetime


class EventOut(BaseModel):
    id: uuid.UUID
    actor: Ref | None
    kind: str
    from_value: str | None
    to_value: str | None
    created_at: datetime


class LinkOut(BaseModel):
    id: uuid.UUID
    kind: str
    url: str
    title: str | None
    created_at: datetime


class TaskDetail(TaskSummary):
    description: str
    milestone_id: uuid.UUID | None
    reporter: Ref | None
    start_date: date | None
    estimate_hours: Decimal | None
    completed_at: datetime | None
    subtasks: list[TaskSummary]
    depends_on: list[TaskSummary]
    comments: list[CommentOut]
    reviews: list[ReviewOut]
    events: list[EventOut]
    links: list[LinkOut]
    allowed_transitions: list[str]
    can_update: bool = False
    can_review: bool = False
