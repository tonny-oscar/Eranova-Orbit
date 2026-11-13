"""Projects, tasks and the task review workflow."""

import uuid
from datetime import date

from sqlalchemy import ColumnElement, case, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.request_meta import RequestMeta
from app.db.base import utc_now
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed, scope_filter
from app.modules.identity.models import User, UserStatus
from app.modules.notifications.service import notify
from app.modules.products.models import Product
from app.modules.products.service import escape_like
from app.modules.work.models import (
    Milestone,
    Project,
    ProjectMember,
    Task,
    TaskComment,
    TaskDependency,
    TaskEvent,
    TaskLink,
    TaskReview,
    TaskStatus,
)
from app.modules.work.schemas import (
    LinkIn,
    MemberIn,
    MilestoneIn,
    ProjectIn,
    ProjectPatch,
    ReviewIn,
    TaskIn,
    TaskPatch,
    TransitionIn,
)

OPEN_STATUSES = (
    TaskStatus.CREATED,
    TaskStatus.ASSIGNED,
    TaskStatus.IN_PROGRESS,
    TaskStatus.SUBMITTED,
    TaskStatus.UNDER_REVIEW,
    TaskStatus.REVISION_REQUESTED,
    TaskStatus.APPROVED,
)
CLOSED_STATUSES = (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
PRIORITY_ORDER = case(
    (Task.priority == "critical", 0),
    (Task.priority == "high", 1),
    (Task.priority == "medium", 2),
    else_=3,
)


# --- Access ------------------------------------------------------------------------


def project_context(project: Project) -> ResourceContext:
    return ResourceContext(
        company_id=project.company_id,
        product_ids=frozenset({project.product_id}) if project.product_id else frozenset(),
        project_id=project.id,
        owner_user_id=project.manager_user_id,
    )


def task_context(task: Task, project: Project) -> ResourceContext:
    return ResourceContext(
        company_id=task.company_id,
        product_ids=frozenset({project.product_id}) if project.product_id else frozenset(),
        project_id=project.id,
        owner_user_id=task.assignee_user_id,
    )


def project_scope(principal: Principal, permission: str) -> ColumnElement[bool]:
    scope = scope_filter(principal, permission)
    if scope.company_wide:
        return true()
    conditions: list[ColumnElement[bool]] = []
    if scope.product_ids:
        conditions.append(Project.product_id.in_(scope.product_ids))
    if scope.project_ids:
        conditions.append(Project.id.in_(scope.project_ids))
    if scope.own:
        conditions.append(Project.manager_user_id == principal.user_id)
    return or_(*conditions) if conditions else false()


def task_scope(principal: Principal) -> ColumnElement[bool]:
    scope = scope_filter(principal, "task.read")
    if scope.company_wide:
        return true()
    conditions: list[ColumnElement[bool]] = []
    if scope.product_ids:
        conditions.append(
            Task.project_id.in_(select(Project.id).where(Project.product_id.in_(scope.product_ids)))
        )
    if scope.project_ids:
        conditions.append(Task.project_id.in_(scope.project_ids))
    if scope.own:
        conditions.append(Task.assignee_user_id == principal.user_id)
    return or_(*conditions) if conditions else false()


async def project_exists(
    session: AsyncSession, company_id: uuid.UUID, project_id: uuid.UUID
) -> bool:
    return bool(
        await session.scalar(
            select(Project.id).where(Project.id == project_id, Project.company_id == company_id)
        )
    )


async def _active_user(
    session: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID | None
) -> User | None:
    if user_id is None:
        return None
    user = await session.scalar(
        select(User).where(User.id == user_id, User.company_id == company_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise AppError("The selected person is not an active user.", code="invalid_user")
    return user


async def _audit(
    session, actor: User, action: str, resource_type: str, resource_id, meta, details=None
):
    await record_event(
        session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type=resource_type,
        resource_id=resource_id,
        meta=meta,
        details=details or {},
    )


# --- Projects ----------------------------------------------------------------------


async def get_project(
    session: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    permission: str = "project.read",
) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.company_id == principal.company_id)
    )
    if project is None or not is_allowed(principal, "project.read", project_context(project)):
        raise NotFoundError("Project not found.")
    if permission != "project.read" and not is_allowed(
        principal, permission, project_context(project)
    ):
        raise PermissionDeniedError("You cannot change this project.")
    return project


async def list_projects(
    session: AsyncSession,
    principal: Principal,
    *,
    q: str | None,
    status: str | None,
    product_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Project], int]:
    conditions = [
        Project.company_id == principal.company_id,
        project_scope(principal, "project.read"),
    ]
    if status:
        conditions.append(Project.status == status)
    if product_id:
        conditions.append(Project.product_id == product_id)
    if q and q.strip():
        conditions.append(
            func.lower(Project.name).like(f"%{escape_like(q.strip().lower())}%", escape="\\")
        )
    total = await session.scalar(select(func.count()).select_from(Project).where(*conditions))
    rows = await session.scalars(
        select(Project)
        .where(*conditions)
        .order_by(
            case((Project.status == "active", 0), else_=1),
            Project.due_date.nulls_last(),
            Project.name,
        )
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def task_counts(session: AsyncSession, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    if not project_ids:
        return {}
    today = date.today()
    rows = await session.execute(
        select(
            Task.project_id,
            func.count(),
            func.count().filter(Task.status.in_(OPEN_STATUSES)),
            func.count().filter(Task.status.in_(OPEN_STATUSES), Task.due_date < today),
            func.count().filter(Task.status.in_((TaskStatus.SUBMITTED, TaskStatus.UNDER_REVIEW))),
            func.count().filter(Task.status == TaskStatus.COMPLETED),
        )
        .where(Task.project_id.in_(project_ids), Task.parent_task_id.is_(None))
        .group_by(Task.project_id)
    )
    return {
        pid: {"total": t, "open": o, "overdue": od, "awaiting_review": r, "completed": c}
        for pid, t, o, od, r, c in rows
    }


async def create_project(
    session: AsyncSession, actor: User, principal: Principal, payload: ProjectIn, meta: RequestMeta
) -> Project:
    context = ResourceContext(
        company_id=actor.company_id,
        product_ids=frozenset({payload.product_id}) if payload.product_id else frozenset(),
    )
    if not is_allowed(principal, "project.create", context):
        raise PermissionDeniedError("You cannot create projects here.")
    if payload.product_id and not await session.scalar(
        select(Product.id).where(
            Product.id == payload.product_id, Product.company_id == actor.company_id
        )
    ):
        raise AppError("Product not found.", code="invalid_product")
    if await session.scalar(
        select(Project.id).where(
            Project.company_id == actor.company_id,
            func.lower(Project.name) == payload.name.strip().lower(),
        )
    ):
        raise ConflictError("A project with this name already exists.", code="project_name_taken")
    await _active_user(session, actor.company_id, payload.manager_user_id)
    project = Project(
        company_id=actor.company_id,
        created_by_user_id=actor.id,
        **payload.model_dump(exclude={"manager_user_id"}),
        manager_user_id=payload.manager_user_id or actor.id,
    )
    project.name = project.name.strip()
    session.add(project)
    await session.flush()
    session.add(
        ProjectMember(
            project_id=project.id, user_id=project.manager_user_id, role_label="Project manager"
        )
    )
    await _audit(
        session, actor, "project.create", "project", project.id, meta, {"name": project.name}
    )
    await session.commit()
    return project


async def update_project(
    session: AsyncSession,
    actor: User,
    principal: Principal,
    project_id: uuid.UUID,
    payload: ProjectPatch,
    meta: RequestMeta,
) -> Project:
    project = await get_project(session, principal, project_id, "project.update")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise AppError("Name cannot be empty.", code="invalid_field")
    if changes.get("manager_user_id"):
        await _active_user(session, actor.company_id, changes["manager_user_id"])
    for field, value in changes.items():
        if field == "description" and value is None:
            value = ""
        setattr(project, field, value)
    await _audit(
        session, actor, "project.update", "project", project.id, meta, {"fields": sorted(changes)}
    )
    await session.commit()
    await session.refresh(project)
    return project


async def add_member(session, actor, principal, project_id, payload: MemberIn, meta) -> None:
    project = await get_project(session, principal, project_id, "project.update")
    user = await _active_user(session, actor.company_id, payload.user_id)
    if await session.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project.id, ProjectMember.user_id == user.id
        )
    ):
        raise ConflictError("Already a member.", code="duplicate_member")
    session.add(
        ProjectMember(project_id=project.id, user_id=user.id, role_label=payload.role_label.strip())
    )
    await notify(
        session,
        company_id=actor.company_id,
        user_ids=[user.id],
        kind="project.member_added",
        title=f"You were added to project {project.name}",
        link=f"/app/projects/{project.id}",
        exclude=actor.id,
    )
    await _audit(
        session, actor, "project.member.add", "project", project.id, meta, {"user_id": str(user.id)}
    )
    await session.commit()


async def remove_member(session, actor, principal, project_id, member_id, meta) -> None:
    project = await get_project(session, principal, project_id, "project.update")
    member = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.id == member_id, ProjectMember.project_id == project.id
        )
    )
    if member is None:
        raise NotFoundError("Member not found.")
    await session.delete(member)
    await _audit(session, actor, "project.member.remove", "project", project.id, meta)
    await session.commit()


async def upsert_milestone(
    session, actor, principal, project_id, payload: MilestoneIn, meta, milestone_id=None
) -> None:
    project = await get_project(session, principal, project_id, "project.update")
    if milestone_id:
        milestone = await session.scalar(
            select(Milestone).where(
                Milestone.id == milestone_id, Milestone.project_id == project.id
            )
        )
        if milestone is None:
            raise NotFoundError("Milestone not found.")
    else:
        milestone = Milestone(project_id=project.id)
        session.add(milestone)
    milestone.title = payload.title.strip()
    milestone.due_date = payload.due_date
    milestone.completed_at = (milestone.completed_at or utc_now()) if payload.completed else None
    await _audit(
        session,
        actor,
        "project.milestone.save",
        "project",
        project.id,
        meta,
        {"title": milestone.title},
    )
    await session.commit()


# --- Tasks --------------------------------------------------------------------------


async def get_task(
    session: AsyncSession, principal: Principal, task_id: uuid.UUID
) -> tuple[Task, Project]:
    row = (
        await session.execute(
            select(Task, Project)
            .join(Project, Project.id == Task.project_id)
            .where(Task.id == task_id, Task.company_id == principal.company_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Task not found.")
    task, project = row
    if not is_allowed(principal, "task.read", task_context(task, project)):
        raise NotFoundError("Task not found.")
    return task, project


async def list_tasks(
    session: AsyncSession,
    principal: Principal,
    *,
    project_id: uuid.UUID | None,
    assignee_id: uuid.UUID | None,
    status: str | None,
    open_only: bool,
    overdue_only: bool,
    q: str | None,
    top_level_only: bool,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Task, Project]], int]:
    conditions = [Task.company_id == principal.company_id, task_scope(principal)]
    if project_id:
        conditions.append(Task.project_id == project_id)
    if assignee_id:
        conditions.append(Task.assignee_user_id == assignee_id)
    if status:
        conditions.append(Task.status == status)
    if open_only:
        conditions.append(Task.status.in_(OPEN_STATUSES))
    if overdue_only:
        conditions.append(Task.status.in_(OPEN_STATUSES))
        conditions.append(Task.due_date < date.today())
    if top_level_only:
        conditions.append(Task.parent_task_id.is_(None))
    if q and q.strip():
        conditions.append(
            func.lower(Task.title).like(f"%{escape_like(q.strip().lower())}%", escape="\\")
        )
    total = await session.scalar(select(func.count()).select_from(Task).where(*conditions))
    rows = await session.execute(
        select(Task, Project)
        .join(Project, Project.id == Task.project_id)
        .where(*conditions)
        .order_by(Task.due_date.nulls_last(), PRIORITY_ORDER, Task.created_at)
        .limit(limit)
        .offset(offset)
    )
    return [(t, p) for t, p in rows], total or 0


def _event(session, task: Task, actor: User, kind: str, from_value=None, to_value=None) -> None:
    session.add(
        TaskEvent(
            task_id=task.id,
            actor_user_id=actor.id,
            kind=kind,
            from_value=str(from_value)[:200] if from_value is not None else None,
            to_value=str(to_value)[:200] if to_value is not None else None,
        )
    )


async def create_task(session, actor: User, principal: Principal, payload: TaskIn, meta) -> Task:
    project = await get_project(session, principal, payload.project_id)
    context = ResourceContext(
        company_id=actor.company_id,
        product_ids=frozenset({project.product_id}) if project.product_id else frozenset(),
        project_id=project.id,
        owner_user_id=payload.assignee_user_id or actor.id,
    )
    if not is_allowed(principal, "task.create", context):
        raise PermissionDeniedError("You cannot create tasks in this project.")
    if payload.parent_task_id:
        parent = await session.scalar(select(Task).where(Task.id == payload.parent_task_id))
        if parent is None or parent.project_id != project.id:
            raise AppError(
                "The parent task must belong to the same project.", code="invalid_parent"
            )
    if payload.milestone_id and not await session.scalar(
        select(Milestone.id).where(
            Milestone.id == payload.milestone_id, Milestone.project_id == project.id
        )
    ):
        raise AppError("Milestone not found in this project.", code="invalid_milestone")
    assignee = await _active_user(session, actor.company_id, payload.assignee_user_id)
    task = Task(
        company_id=actor.company_id,
        reporter_user_id=actor.id,
        status=TaskStatus.ASSIGNED if assignee else TaskStatus.CREATED,
        **payload.model_dump(),
    )
    task.title = task.title.strip()
    session.add(task)
    await session.flush()
    _event(session, task, actor, "created", None, task.status)
    if assignee:
        await notify(
            session,
            company_id=actor.company_id,
            user_ids=[assignee.id],
            kind="task.assigned",
            title=f"New task: {task.title}",
            body=f"Project {project.name}",
            link=f"/app/tasks/{task.id}",
            exclude=actor.id,
        )
    await _audit(
        session, actor, "task.create", "task", task.id, meta, {"project_id": str(project.id)}
    )
    await session.commit()
    return task


async def update_task(
    session, actor: User, principal: Principal, task_id: uuid.UUID, payload: TaskPatch, meta
) -> Task:
    task, project = await get_task(session, principal, task_id)
    if not is_allowed(principal, "task.update", task_context(task, project)):
        raise PermissionDeniedError("You cannot edit this task.")
    if task.status in CLOSED_STATUSES:
        raise AppError("Closed tasks cannot be edited.", code="task_closed")
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes and not changes["title"]:
        raise AppError("Title cannot be empty.", code="invalid_field")
    if "assignee_user_id" in changes and changes["assignee_user_id"] != task.assignee_user_id:
        assignee = await _active_user(session, actor.company_id, changes["assignee_user_id"])
        _event(
            session, task, actor, "assignment", task.assignee_user_id, changes["assignee_user_id"]
        )
        if assignee:
            if task.status == TaskStatus.CREATED:
                _event(session, task, actor, "status", task.status, TaskStatus.ASSIGNED)
                task.status = TaskStatus.ASSIGNED
            await notify(
                session,
                company_id=actor.company_id,
                user_ids=[assignee.id],
                kind="task.assigned",
                title=f"Task assigned to you: {task.title}",
                link=f"/app/tasks/{task.id}",
                exclude=actor.id,
            )
    if changes.get("milestone_id") and not await session.scalar(
        select(Milestone.id).where(
            Milestone.id == changes["milestone_id"], Milestone.project_id == project.id
        )
    ):
        raise AppError("Milestone not found in this project.", code="invalid_milestone")
    for field, value in changes.items():
        if field == "description" and value is None:
            value = ""
        setattr(task, field, value)
    if any(f not in ("assignee_user_id",) for f in changes):
        _event(session, task, actor, "edit", None, ", ".join(sorted(changes)))
    await _audit(session, actor, "task.update", "task", task.id, meta, {"fields": sorted(changes)})
    await session.commit()
    await session.refresh(task)
    return task


def allowed_transitions(
    task: Task, principal: Principal, project: Project, user_id: uuid.UUID
) -> list[str]:
    context = task_context(task, project)
    is_assignee = task.assignee_user_id == user_id
    can_update = is_allowed(principal, "task.update", context)
    can_review = is_allowed(principal, "task.approve", context) and not is_assignee
    status = task.status
    options: list[str] = []
    if is_assignee and status in (TaskStatus.ASSIGNED, TaskStatus.REVISION_REQUESTED):
        options.append("in_progress")
    if is_assignee and status == TaskStatus.IN_PROGRESS:
        options.append("submitted")
    if can_review and status == TaskStatus.SUBMITTED:
        options.append("under_review")
    if can_update and status == TaskStatus.APPROVED:
        options.append("completed")
    if can_update and status not in CLOSED_STATUSES:
        options.append("cancelled")
    return options


async def _blocking_dependencies(session: AsyncSession, task: Task) -> list[str]:
    rows = await session.scalars(
        select(Task.title)
        .join(TaskDependency, TaskDependency.depends_on_task_id == Task.id)
        .where(TaskDependency.task_id == task.id, Task.status != TaskStatus.COMPLETED)
    )
    return list(rows)


async def transition(
    session, actor: User, principal: Principal, task_id: uuid.UUID, payload: TransitionIn, meta
) -> Task:
    task, project = await get_task(session, principal, task_id)
    if payload.to not in allowed_transitions(task, principal, project, actor.id):
        raise PermissionDeniedError(
            f"You cannot move this task from '{task.status}' to '{payload.to}'.",
            code="transition_not_allowed",
        )
    if payload.to == "in_progress":
        blockers = await _blocking_dependencies(session, task)
        if blockers:
            raise ConflictError(
                "This task depends on unfinished work: " + ", ".join(blockers),
                code="blocked_by_dependencies",
            )
    previous = task.status
    task.status = payload.to
    if payload.to == "completed":
        task.completed_at = utc_now()
    _event(session, task, actor, "status", previous, payload.to)
    if payload.note:
        session.add(
            TaskComment(task_id=task.id, author_user_id=actor.id, body=payload.note.strip())
        )
    recipients = {
        "submitted": [project.manager_user_id, task.reporter_user_id],
        "under_review": [task.assignee_user_id],
        "completed": [task.assignee_user_id],
        "cancelled": [task.assignee_user_id],
        "in_progress": [],
    }[payload.to]
    await notify(
        session,
        company_id=actor.company_id,
        user_ids=recipients,
        kind=f"task.{payload.to}",
        title=f"{task.title}: {payload.to.replace('_', ' ')}",
        link=f"/app/tasks/{task.id}",
        exclude=actor.id,
    )
    await _audit(
        session,
        actor,
        "task.transition",
        "task",
        task.id,
        meta,
        {"from": previous, "to": payload.to},
    )
    await session.commit()
    await session.refresh(task)
    return task


async def review(
    session, actor: User, principal: Principal, task_id: uuid.UUID, payload: ReviewIn, meta
) -> Task:
    task, project = await get_task(session, principal, task_id)
    if task.assignee_user_id == actor.id:
        raise PermissionDeniedError("You cannot review your own work.", code="self_review")
    if not is_allowed(principal, "task.approve", task_context(task, project)):
        raise PermissionDeniedError("You cannot review tasks in this project.")
    if task.status not in (TaskStatus.SUBMITTED, TaskStatus.UNDER_REVIEW):
        raise AppError("Only submitted work can be reviewed.", code="not_in_review")
    if payload.decision == "revision_requested" and not payload.comment.strip():
        raise AppError("Explain what needs to change.", code="comment_required")
    session.add(
        TaskReview(
            task_id=task.id,
            reviewer_user_id=actor.id,
            decision=payload.decision,
            comment=payload.comment.strip(),
        )
    )
    previous = task.status
    task.status = payload.decision
    _event(session, task, actor, "review", previous, payload.decision)
    await notify(
        session,
        company_id=actor.company_id,
        user_ids=[task.assignee_user_id],
        kind=f"task.{payload.decision}",
        title=f"{task.title}: {payload.decision.replace('_', ' ')}",
        body=payload.comment,
        link=f"/app/tasks/{task.id}",
        exclude=actor.id,
    )
    await _audit(
        session, actor, "task.review", "task", task.id, meta, {"decision": payload.decision}
    )
    await session.commit()
    await session.refresh(task)
    return task


async def add_comment(
    session, actor: User, principal: Principal, task_id: uuid.UUID, body: str
) -> None:
    task, _project = await get_task(session, principal, task_id)
    session.add(TaskComment(task_id=task.id, author_user_id=actor.id, body=body.strip()))
    _event(session, task, actor, "comment")
    await notify(
        session,
        company_id=actor.company_id,
        user_ids=[task.assignee_user_id, task.reporter_user_id],
        kind="task.comment",
        title=f"New comment on {task.title}",
        body=body[:200],
        link=f"/app/tasks/{task.id}",
        exclude=actor.id,
    )
    await session.commit()


async def _creates_cycle(session: AsyncSession, task_id: uuid.UUID, depends_on: uuid.UUID) -> bool:
    frontier, seen = [depends_on], set()
    while frontier:
        current = frontier.pop()
        if current == task_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(
            await session.scalars(
                select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == current)
            )
        )
    return False


async def add_dependency(session, actor, principal, task_id, depends_on_id, meta) -> None:
    task, project = await get_task(session, principal, task_id)
    if not is_allowed(principal, "task.update", task_context(task, project)):
        raise PermissionDeniedError("You cannot edit this task.")
    other, _ = await get_task(session, principal, depends_on_id)
    if other.id == task.id or await _creates_cycle(session, task.id, other.id):
        raise AppError("That dependency would create a loop.", code="dependency_cycle")
    if await session.scalar(
        select(TaskDependency.id).where(
            TaskDependency.task_id == task.id, TaskDependency.depends_on_task_id == other.id
        )
    ):
        raise ConflictError("Dependency already exists.", code="duplicate_dependency")
    session.add(TaskDependency(task_id=task.id, depends_on_task_id=other.id))
    _event(session, task, actor, "dependency", None, other.title)
    await session.commit()


async def remove_dependency(session, actor, principal, task_id, depends_on_id) -> None:
    task, project = await get_task(session, principal, task_id)
    if not is_allowed(principal, "task.update", task_context(task, project)):
        raise PermissionDeniedError("You cannot edit this task.")
    dep = await session.scalar(
        select(TaskDependency).where(
            TaskDependency.task_id == task.id, TaskDependency.depends_on_task_id == depends_on_id
        )
    )
    if dep is None:
        raise NotFoundError("Dependency not found.")
    await session.delete(dep)
    await session.commit()


async def add_link(
    session, actor, principal, task_id, payload: LinkIn, external_ref: str | None = None
) -> TaskLink:
    task, _project = await get_task(session, principal, task_id)
    link = TaskLink(
        task_id=task.id,
        kind=payload.kind,
        url=payload.url,
        title=payload.title,
        external_ref=external_ref,
        created_by_user_id=actor.id if actor else None,
    )
    session.add(link)
    if actor:
        _event(session, task, actor, "link", None, payload.kind)
    await session.commit()
    return link


async def remove_link(session, actor, principal, task_id, link_id) -> None:
    task, project = await get_task(session, principal, task_id)
    link = await session.scalar(
        select(TaskLink).where(TaskLink.id == link_id, TaskLink.task_id == task.id)
    )
    if link is None:
        raise NotFoundError("Link not found.")
    if link.created_by_user_id != actor.id and not is_allowed(
        principal, "task.update", task_context(task, project)
    ):
        raise PermissionDeniedError("You cannot remove this link.")
    await session.delete(link)
    await session.commit()
