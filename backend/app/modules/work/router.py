import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_request_meta, require_permission
from app.api.pagination import Page, PageParams, page_params
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.authorization.policy import ResourceContext, is_allowed
from app.modules.identity.models import User
from app.modules.products.models import Product
from app.modules.work import service
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
)
from app.modules.work.schemas import (
    CommentIn,
    CommentOut,
    DependencyIn,
    EventOut,
    LinkIn,
    LinkOut,
    MemberIn,
    MemberOut,
    MilestoneIn,
    MilestoneOut,
    ProjectDetail,
    ProjectIn,
    ProjectPatch,
    ProjectSummary,
    Ref,
    ReviewIn,
    ReviewOut,
    TaskCounts,
    TaskDetail,
    TaskIn,
    TaskPatch,
    TaskSummary,
    TransitionIn,
)

router = APIRouter(tags=["work"])


async def _names(db: AsyncSession, model, ids) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    label = model.full_name if model is User else model.name
    return {
        row.id: row.name
        for row in (
            await db.execute(select(model.id, label.label("name")).where(model.id.in_(ids)))
        )
    }


def _ref(names: dict, key) -> Ref | None:
    return Ref(id=key, name=names[key]) if key in names else None


async def _project_summaries(db: AsyncSession, projects: list[Project]) -> list[ProjectSummary]:
    products = await _names(db, Product, {p.product_id for p in projects})
    users = await _names(db, User, {p.manager_user_id for p in projects})
    counts = await service.task_counts(db, [p.id for p in projects])
    return [
        ProjectSummary(
            id=p.id,
            name=p.name,
            status=p.status,
            priority=p.priority,
            product=_ref(products, p.product_id),
            manager=_ref(users, p.manager_user_id),
            start_date=p.start_date,
            due_date=p.due_date,
            tasks=TaskCounts(**counts.get(p.id, {})),
        )
        for p in projects
    ]


async def _project_detail(db: AsyncSession, auth: AuthContext, project: Project) -> ProjectDetail:
    summary = (await _project_summaries(db, [project]))[0]
    members = (
        await db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project.id)
            .order_by(User.full_name)
        )
    ).all()
    milestones = list(
        await db.scalars(
            select(Milestone)
            .where(Milestone.project_id == project.id)
            .order_by(Milestone.due_date.nulls_last())
        )
    )
    context = service.project_context(project)
    return ProjectDetail(
        **summary.model_dump(),
        description=project.description,
        budget_amount=project.budget_amount,
        budget_currency=project.budget_currency,
        repository_url=project.repository_url,
        docs_url=project.docs_url,
        members=[
            MemberOut(id=m.id, user=Ref(id=u.id, name=u.full_name), role_label=m.role_label)
            for m, u in members
        ],
        milestones=[
            MilestoneOut(id=m.id, title=m.title, due_date=m.due_date, completed_at=m.completed_at)
            for m in milestones
        ],
        can_update=is_allowed(auth.principal, "project.update", context),
        can_create_tasks=is_allowed(
            auth.principal,
            "task.create",
            ResourceContext(
                company_id=project.company_id,
                product_ids=context.product_ids,
                project_id=project.id,
                owner_user_id=auth.user.id,
            ),
        ),
    )


async def _task_summaries(db: AsyncSession, rows: list[tuple[Task, Project]]) -> list[TaskSummary]:
    users = await _names(db, User, {t.assignee_user_id for t, _ in rows})
    today = date.today()
    return [
        TaskSummary(
            id=t.id,
            title=t.title,
            status=t.status,
            priority=t.priority,
            project=Ref(id=p.id, name=p.name),
            assignee=_ref(users, t.assignee_user_id),
            due_date=t.due_date,
            parent_task_id=t.parent_task_id,
            is_overdue=bool(
                t.due_date and t.due_date < today and t.status in service.OPEN_STATUSES
            ),
            updated_at=t.updated_at,
        )
        for t, p in rows
    ]


async def _task_detail(
    db: AsyncSession, auth: AuthContext, task: Task, project: Project
) -> TaskDetail:
    summary = (await _task_summaries(db, [(task, project)]))[0]
    subtasks = list(
        await db.scalars(
            select(Task).where(Task.parent_task_id == task.id).order_by(Task.created_at)
        )
    )
    deps = list(
        await db.scalars(
            select(Task)
            .join(TaskDependency, TaskDependency.depends_on_task_id == Task.id)
            .where(TaskDependency.task_id == task.id)
        )
    )
    comments = list(
        await db.scalars(
            select(TaskComment)
            .where(TaskComment.task_id == task.id)
            .order_by(TaskComment.created_at)
        )
    )
    reviews = list(
        await db.scalars(
            select(TaskReview)
            .where(TaskReview.task_id == task.id)
            .order_by(TaskReview.created_at.desc())
        )
    )
    events = list(
        await db.scalars(
            select(TaskEvent)
            .where(TaskEvent.task_id == task.id)
            .order_by(TaskEvent.created_at.desc())
        )
    )
    links = list(
        await db.scalars(
            select(TaskLink).where(TaskLink.task_id == task.id).order_by(TaskLink.created_at)
        )
    )
    people = await _names(
        db,
        User,
        {task.reporter_user_id}
        | {c.author_user_id for c in comments}
        | {r.reviewer_user_id for r in reviews}
        | {e.actor_user_id for e in events},
    )
    context = service.task_context(task, project)
    return TaskDetail(
        **summary.model_dump(),
        description=task.description,
        milestone_id=task.milestone_id,
        reporter=_ref(people, task.reporter_user_id),
        start_date=task.start_date,
        estimate_hours=task.estimate_hours,
        completed_at=task.completed_at,
        subtasks=await _task_summaries(db, [(s, project) for s in subtasks]),
        depends_on=await _task_summaries(db, [(d, project) for d in deps]),
        comments=[
            CommentOut(
                id=c.id, author=_ref(people, c.author_user_id), body=c.body, created_at=c.created_at
            )
            for c in comments
        ],
        reviews=[
            ReviewOut(
                id=r.id,
                reviewer=_ref(people, r.reviewer_user_id),
                decision=r.decision,
                comment=r.comment,
                created_at=r.created_at,
            )
            for r in reviews
        ],
        events=[
            EventOut(
                id=e.id,
                actor=_ref(people, e.actor_user_id),
                kind=e.kind,
                from_value=e.from_value,
                to_value=e.to_value,
                created_at=e.created_at,
            )
            for e in events
        ],
        links=[
            LinkOut(id=lk.id, kind=lk.kind, url=lk.url, title=lk.title, created_at=lk.created_at)
            for lk in links
        ],
        allowed_transitions=service.allowed_transitions(
            task, auth.principal, project, auth.user.id
        ),
        can_update=is_allowed(auth.principal, "task.update", context)
        and task.status not in service.CLOSED_STATUSES,
        can_review=is_allowed(auth.principal, "task.approve", context)
        and task.assignee_user_id != auth.user.id
        and task.status in ("submitted", "under_review"),
    )


# --- Projects ----------------------------------------------------------------------


@router.get("/projects", response_model=Page[ProjectSummary])
async def list_projects(
    q: str | None = Query(None, max_length=100),
    project_status: str | None = Query(None, alias="status", max_length=20),
    product_id: uuid.UUID | None = None,
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("project.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[ProjectSummary]:
    rows, total = await service.list_projects(
        db,
        auth.principal,
        q=q,
        status=project_status,
        product_id=product_id,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=await _project_summaries(db, rows), total=total, limit=page.limit, offset=page.offset
    )


@router.post("/projects", response_model=ProjectDetail, status_code=201)
async def create_project(
    payload: ProjectIn,
    auth: AuthContext = Depends(require_permission("project.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProjectDetail:
    project = await service.create_project(db, auth.user, auth.principal, payload, meta)
    return await _project_detail(db, auth, project)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("project.read")),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetail:
    return await _project_detail(
        db, auth, await service.get_project(db, auth.principal, project_id)
    )


@router.patch("/projects/{project_id}", response_model=ProjectDetail)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectPatch,
    auth: AuthContext = Depends(require_permission("project.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProjectDetail:
    project = await service.update_project(db, auth.user, auth.principal, project_id, payload, meta)
    return await _project_detail(db, auth, project)


@router.post("/projects/{project_id}/members", response_model=ProjectDetail, status_code=201)
async def add_member(
    project_id: uuid.UUID,
    payload: MemberIn,
    auth: AuthContext = Depends(require_permission("project.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProjectDetail:
    await service.add_member(db, auth.user, auth.principal, project_id, payload, meta)
    return await _project_detail(
        db, auth, await service.get_project(db, auth.principal, project_id)
    )


@router.delete("/projects/{project_id}/members/{member_id}", response_model=ProjectDetail)
async def remove_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("project.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProjectDetail:
    await service.remove_member(db, auth.user, auth.principal, project_id, member_id, meta)
    return await _project_detail(
        db, auth, await service.get_project(db, auth.principal, project_id)
    )


@router.post("/projects/{project_id}/milestones", response_model=ProjectDetail, status_code=201)
async def add_milestone(
    project_id: uuid.UUID,
    payload: MilestoneIn,
    auth: AuthContext = Depends(require_permission("project.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProjectDetail:
    await service.upsert_milestone(db, auth.user, auth.principal, project_id, payload, meta)
    return await _project_detail(
        db, auth, await service.get_project(db, auth.principal, project_id)
    )


@router.put("/projects/{project_id}/milestones/{milestone_id}", response_model=ProjectDetail)
async def update_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    payload: MilestoneIn,
    auth: AuthContext = Depends(require_permission("project.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProjectDetail:
    await service.upsert_milestone(
        db, auth.user, auth.principal, project_id, payload, meta, milestone_id
    )
    return await _project_detail(
        db, auth, await service.get_project(db, auth.principal, project_id)
    )


# --- Tasks --------------------------------------------------------------------------


@router.get("/tasks", response_model=Page[TaskSummary])
async def list_tasks(
    project_id: uuid.UUID | None = None,
    mine: bool = False,
    task_status: str | None = Query(None, alias="status", max_length=30),
    open_only: bool = False,
    overdue: bool = False,
    top_level: bool = True,
    q: str | None = Query(None, max_length=100),
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Page[TaskSummary]:
    rows, total = await service.list_tasks(
        db,
        auth.principal,
        project_id=project_id,
        assignee_id=auth.user.id if mine else None,
        status=task_status,
        open_only=open_only,
        overdue_only=overdue,
        q=q,
        top_level_only=top_level and project_id is not None,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=await _task_summaries(db, rows), total=total, limit=page.limit, offset=page.offset
    )


@router.post("/tasks", response_model=TaskDetail, status_code=201)
async def create_task(
    payload: TaskIn,
    auth: AuthContext = Depends(require_permission("task.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TaskDetail:
    task = await service.create_task(db, auth.user, auth.principal, payload, meta)
    task, project = await service.get_task(db, auth.principal, task.id)
    return await _task_detail(db, auth, task, project)


async def _detail_for(db, auth, task_id) -> TaskDetail:
    task, project = await service.get_task(db, auth.principal, task_id)
    return await _task_detail(db, auth, task, project)


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> TaskDetail:
    return await _detail_for(db, auth, task_id)


@router.patch("/tasks/{task_id}", response_model=TaskDetail)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskPatch,
    auth: AuthContext = Depends(require_permission("task.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TaskDetail:
    await service.update_task(db, auth.user, auth.principal, task_id, payload, meta)
    return await _detail_for(db, auth, task_id)


@router.post("/tasks/{task_id}/transition", response_model=TaskDetail)
async def transition_task(
    task_id: uuid.UUID,
    payload: TransitionIn,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TaskDetail:
    await service.transition(db, auth.user, auth.principal, task_id, payload, meta)
    return await _detail_for(db, auth, task_id)


@router.post("/tasks/{task_id}/review", response_model=TaskDetail)
async def review_task(
    task_id: uuid.UUID,
    payload: ReviewIn,
    auth: AuthContext = Depends(require_permission("task.approve")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TaskDetail:
    await service.review(db, auth.user, auth.principal, task_id, payload, meta)
    return await _detail_for(db, auth, task_id)


@router.post("/tasks/{task_id}/comments", response_model=TaskDetail, status_code=201)
async def comment_task(
    task_id: uuid.UUID,
    payload: CommentIn,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> TaskDetail:
    await service.add_comment(db, auth.user, auth.principal, task_id, payload.body)
    return await _detail_for(db, auth, task_id)


@router.post("/tasks/{task_id}/dependencies", response_model=TaskDetail, status_code=201)
async def add_dependency(
    task_id: uuid.UUID,
    payload: DependencyIn,
    auth: AuthContext = Depends(require_permission("task.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> TaskDetail:
    await service.add_dependency(
        db, auth.user, auth.principal, task_id, payload.depends_on_task_id, meta
    )
    return await _detail_for(db, auth, task_id)


@router.delete("/tasks/{task_id}/dependencies/{depends_on_id}", response_model=TaskDetail)
async def remove_dependency(
    task_id: uuid.UUID,
    depends_on_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("task.update")),
    db: AsyncSession = Depends(get_db),
) -> TaskDetail:
    await service.remove_dependency(db, auth.user, auth.principal, task_id, depends_on_id)
    return await _detail_for(db, auth, task_id)


@router.post("/tasks/{task_id}/links", response_model=TaskDetail, status_code=201)
async def add_link(
    task_id: uuid.UUID,
    payload: LinkIn,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> TaskDetail:
    await service.add_link(db, auth.user, auth.principal, task_id, payload)
    return await _detail_for(db, auth, task_id)


@router.delete("/tasks/{task_id}/links/{link_id}", status_code=204)
async def remove_link(
    task_id: uuid.UUID,
    link_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await service.remove_link(db, auth.user, auth.principal, task_id, link_id)
    return Response(status_code=204)
