import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.api.pagination import Page, PageParams, page_params
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.identity.models import User
from app.modules.people import service
from app.modules.people.schemas import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentRef,
    DepartmentUpdate,
    EmployeeOut,
    EmployeeUpdate,
    PersonRef,
)

router = APIRouter(tags=["people"])


def _person(user: User | None) -> PersonRef | None:
    if user is None:
        return None
    return PersonRef(id=user.id, full_name=user.full_name, email=user.email)


def _employee_out(row: service.EmployeeRow, can_update: bool = False) -> EmployeeOut:
    profile = row.profile
    return EmployeeOut(
        user=_person(row.user),
        status=row.user.status,
        department=DepartmentRef(id=row.department.id, name=row.department.name)
        if row.department
        else None,
        job_title=profile.job_title if profile else None,
        manager=_person(row.manager),
        employment_type=profile.employment_type if profile else None,
        start_date=profile.start_date if profile else None,
        has_profile=profile is not None,
        can_update=can_update,
    )


def _department_out(view: service.DepartmentView) -> DepartmentOut:
    return DepartmentOut(
        id=view.department.id,
        name=view.department.name,
        description=view.department.description,
        head=_person(view.head),
        member_count=view.member_count,
        created_at=view.department.created_at,
    )


@router.get("/employees", response_model=Page[EmployeeOut])
async def list_employees(
    q: str | None = Query(None, max_length=100),
    department_id: uuid.UUID | None = None,
    include_disabled: bool = False,
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("employee.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[EmployeeOut]:
    rows, total = await service.list_employees(
        db,
        auth.principal,
        q=q,
        department_id=department_id,
        include_disabled=include_disabled,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[_employee_out(r) for r in rows], total=total, limit=page.limit, offset=page.offset
    )


@router.get("/employees/{user_id}", response_model=EmployeeOut)
async def get_employee(
    user_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("employee.read")),
    db: AsyncSession = Depends(get_db),
) -> EmployeeOut:
    row = await service.get_employee(db, auth.principal, user_id)
    return _employee_out(row, service.can_update_employee(auth.principal, row))


@router.put("/employees/{user_id}", response_model=EmployeeOut)
async def update_employee(
    user_id: uuid.UUID,
    payload: EmployeeUpdate,
    auth: AuthContext = Depends(require_permission("employee.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> EmployeeOut:
    row = await service.update_employee(
        db, actor=auth.user, principal=auth.principal, user_id=user_id, payload=payload, meta=meta
    )
    return _employee_out(row, service.can_update_employee(auth.principal, row))


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(
    auth: AuthContext = Depends(require_permission("employee.read")),
    db: AsyncSession = Depends(get_db),
) -> list[DepartmentOut]:
    return [_department_out(v) for v in await service.list_departments(db, auth.user.company_id)]


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    auth: AuthContext = Depends(require_permission("employee.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> DepartmentOut:
    view = await service.create_department(
        db,
        actor=auth.user,
        principal=auth.principal,
        name=payload.name,
        description=payload.description,
        head_user_id=payload.head_user_id,
        meta=meta,
    )
    return _department_out(view)


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    auth: AuthContext = Depends(require_permission("employee.manage")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> DepartmentOut:
    view = await service.update_department(
        db,
        actor=auth.user,
        principal=auth.principal,
        department_id=department_id,
        changes=payload.model_dump(exclude_unset=True),
        meta=meta,
    )
    return _department_out(view)
