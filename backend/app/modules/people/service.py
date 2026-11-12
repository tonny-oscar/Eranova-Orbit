import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.request_meta import RequestMeta
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import (
    Principal,
    ResourceContext,
    is_allowed,
    scope_filter,
)
from app.modules.identity.models import User, UserStatus
from app.modules.people.models import Department, EmployeeProfile
from app.modules.people.schemas import EmployeeUpdate

_MAX_MANAGER_DEPTH = 50


def employee_context(company_id: uuid.UUID, user_id: uuid.UUID, department_id: uuid.UUID | None):
    return ResourceContext(
        company_id=company_id, department_id=department_id, owner_user_id=user_id
    )


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def department_member_condition(principal: Principal, permission: str) -> ColumnElement[bool]:
    """Users visible under ``permission``: company-wide, by department, or self."""
    scope = scope_filter(principal, permission)
    if scope.company_wide:
        return true()
    conditions: list[ColumnElement[bool]] = []
    if scope.department_ids:
        conditions.append(
            User.id.in_(
                select(EmployeeProfile.user_id).where(
                    EmployeeProfile.department_id.in_(scope.department_ids)
                )
            )
        )
    if scope.own:
        conditions.append(User.id == principal.user_id)
    return or_(*conditions) if conditions else false()


@dataclass
class EmployeeRow:
    user: User
    profile: EmployeeProfile | None
    department: Department | None
    manager: User | None


def _employee_query():
    manager = aliased(User)
    return (
        select(User, EmployeeProfile, Department, manager)
        .outerjoin(EmployeeProfile, EmployeeProfile.user_id == User.id)
        .outerjoin(Department, Department.id == EmployeeProfile.department_id)
        .outerjoin(manager, manager.id == EmployeeProfile.manager_user_id)
    )


async def list_employees(
    session: AsyncSession,
    principal: Principal,
    *,
    q: str | None,
    department_id: uuid.UUID | None,
    include_disabled: bool,
    limit: int,
    offset: int,
) -> tuple[list[EmployeeRow], int]:
    conditions = [
        User.company_id == principal.company_id,
        department_member_condition(principal, "employee.read"),
    ]
    if not include_disabled:
        conditions.append(User.status != UserStatus.DISABLED)
    if department_id:
        conditions.append(
            User.id.in_(
                select(EmployeeProfile.user_id).where(
                    EmployeeProfile.department_id == department_id
                )
            )
        )
    if q and q.strip():
        pattern = f"%{escape_like(q.strip().lower())}%"
        conditions.append(
            or_(
                func.lower(User.full_name).like(pattern, escape="\\"),
                User.email.like(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(User).where(*conditions))
    rows = await session.execute(
        _employee_query().where(*conditions).order_by(User.full_name).limit(limit).offset(offset)
    )
    return [EmployeeRow(*row) for row in rows], total or 0


async def get_employee(
    session: AsyncSession, principal: Principal, user_id: uuid.UUID
) -> EmployeeRow:
    row = (
        await session.execute(
            _employee_query().where(User.id == user_id, User.company_id == principal.company_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Employee not found.")
    found = EmployeeRow(*row)
    department_id = found.profile.department_id if found.profile else None
    if not is_allowed(
        principal, "employee.read", employee_context(principal.company_id, user_id, department_id)
    ):
        raise NotFoundError("Employee not found.")
    return found


def can_update_employee(principal: Principal, row: EmployeeRow) -> bool:
    department_id = row.profile.department_id if row.profile else None
    return is_allowed(
        principal,
        "employee.update",
        employee_context(principal.company_id, row.user.id, department_id),
    )


async def _check_manager(
    session: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID, manager_id: uuid.UUID
) -> None:
    if manager_id == user_id:
        raise AppError("A person cannot be their own manager.", code="invalid_manager")
    manager = await session.scalar(
        select(User).where(User.id == manager_id, User.company_id == company_id)
    )
    if manager is None or manager.status != UserStatus.ACTIVE:
        raise AppError("The selected manager is not an active user.", code="invalid_manager")
    current: uuid.UUID | None = manager_id
    for _ in range(_MAX_MANAGER_DEPTH):
        current = await session.scalar(
            select(EmployeeProfile.manager_user_id).where(EmployeeProfile.user_id == current)
        )
        if current is None:
            return
        if current == user_id:
            raise AppError("This would create a reporting loop.", code="invalid_manager")
    raise AppError("The reporting chain is too deep.", code="invalid_manager")


async def update_employee(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    user_id: uuid.UUID,
    payload: EmployeeUpdate,
    meta: RequestMeta,
) -> EmployeeRow:
    row = await get_employee(session, principal, user_id)
    if not can_update_employee(principal, row):
        raise PermissionDeniedError("You cannot edit this employee record.")

    if payload.department_id:
        department = await session.scalar(
            select(Department).where(
                Department.id == payload.department_id, Department.company_id == actor.company_id
            )
        )
        if department is None:
            raise AppError("The selected department does not exist.", code="invalid_department")
    current_department = row.profile.department_id if row.profile else None
    if payload.department_id != current_department and not is_allowed(
        principal,
        "employee.update",
        employee_context(actor.company_id, user_id, payload.department_id),
    ):
        raise PermissionDeniedError("You cannot move people into a department outside your access.")
    if payload.manager_user_id:
        await _check_manager(session, actor.company_id, user_id, payload.manager_user_id)

    profile = row.profile
    created = profile is None
    if profile is None:
        profile = EmployeeProfile(user_id=user_id, company_id=actor.company_id)
        session.add(profile)

    new_values = {
        "department_id": payload.department_id,
        "job_title": payload.job_title.strip() if payload.job_title else None,
        "manager_user_id": payload.manager_user_id,
        "employment_type": payload.employment_type,
        "start_date": payload.start_date,
    }
    changes = {}
    for field, value in new_values.items():
        old = None if created else getattr(profile, field)
        if old != value:
            changes[field] = {"from": _jsonable(old), "to": _jsonable(value)}
        setattr(profile, field, value)

    if changes:
        await record_event(
            session,
            action="employee.update",
            outcome=AuditOutcome.SUCCESS,
            actor_user_id=actor.id,
            company_id=actor.company_id,
            resource_type="employee",
            resource_id=user_id,
            meta=meta,
            details={"changes": changes, "created": created},
        )
        await session.commit()
    return await get_employee(session, principal, user_id)


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, str | int | bool):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[union-attr]
    return str(value)


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------


@dataclass
class DepartmentView:
    department: Department
    head: User | None
    member_count: int


async def list_departments(session: AsyncSession, company_id: uuid.UUID) -> list[DepartmentView]:
    counts = (
        select(EmployeeProfile.department_id, func.count().label("members"))
        .join(User, User.id == EmployeeProfile.user_id)
        .where(User.status != UserStatus.DISABLED)
        .group_by(EmployeeProfile.department_id)
        .subquery()
    )
    rows = await session.execute(
        select(Department, User, func.coalesce(counts.c.members, 0))
        .outerjoin(User, User.id == Department.head_user_id)
        .outerjoin(counts, counts.c.department_id == Department.id)
        .where(Department.company_id == company_id)
        .order_by(Department.name)
    )
    return [DepartmentView(d, head, count) for d, head, count in rows]


async def get_department(
    session: AsyncSession, company_id: uuid.UUID, department_id: uuid.UUID
) -> DepartmentView:
    for view in await list_departments(session, company_id):
        if view.department.id == department_id:
            return view
    raise NotFoundError("Department not found.")


def _require_manage(principal: Principal) -> None:
    if not is_allowed(
        principal, "employee.manage", ResourceContext(company_id=principal.company_id)
    ):
        raise PermissionDeniedError("Managing departments requires company-wide access.")


async def _check_name(
    session: AsyncSession, company_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None
) -> None:
    query = select(Department.id).where(
        Department.company_id == company_id, func.lower(Department.name) == name.lower()
    )
    if exclude:
        query = query.where(Department.id != exclude)
    if await session.scalar(query):
        raise ConflictError(
            "A department with this name already exists.",
            code="department_name_taken",
            details=[{"field": "name", "message": "This name is already in use."}],
        )


async def _check_head(session: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID) -> None:
    user = await session.scalar(
        select(User).where(User.id == user_id, User.company_id == company_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise AppError("The department head must be an active user.", code="invalid_head")


async def create_department(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    name: str,
    description: str,
    head_user_id: uuid.UUID | None,
    meta: RequestMeta,
) -> DepartmentView:
    _require_manage(principal)
    name = name.strip()
    await _check_name(session, actor.company_id, name)
    if head_user_id:
        await _check_head(session, actor.company_id, head_user_id)
    department = Department(
        company_id=actor.company_id,
        name=name,
        description=description.strip(),
        head_user_id=head_user_id,
    )
    session.add(department)
    await session.flush()
    await record_event(
        session,
        action="department.create",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="department",
        resource_id=department.id,
        meta=meta,
        details={"name": name},
    )
    await session.commit()
    return await get_department(session, actor.company_id, department.id)


async def update_department(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    department_id: uuid.UUID,
    changes: dict,
    meta: RequestMeta,
) -> DepartmentView:
    _require_manage(principal)
    view = await get_department(session, actor.company_id, department_id)
    department = view.department
    audited = {}
    if changes.get("name") and changes["name"].strip() != department.name:
        await _check_name(session, actor.company_id, changes["name"].strip(), exclude=department.id)
        audited["name"] = {"from": department.name, "to": changes["name"].strip()}
        department.name = changes["name"].strip()
    if "description" in changes and changes["description"] is not None:
        department.description = changes["description"].strip()
    if "head_user_id" in changes and changes["head_user_id"] != department.head_user_id:
        if changes["head_user_id"]:
            await _check_head(session, actor.company_id, changes["head_user_id"])
        audited["head_user_id"] = {
            "from": _jsonable(department.head_user_id),
            "to": _jsonable(changes["head_user_id"]),
        }
        department.head_user_id = changes["head_user_id"]
    if session.is_modified(department):
        await record_event(
            session,
            action="department.update",
            outcome=AuditOutcome.SUCCESS,
            actor_user_id=actor.id,
            company_id=actor.company_id,
            resource_type="department",
            resource_id=department.id,
            meta=meta,
            details={"changes": audited},
        )
        await session.commit()
    return await get_department(session, actor.company_id, department.id)


async def department_exists(
    session: AsyncSession, company_id: uuid.UUID, department_id: uuid.UUID
) -> bool:
    found = await session.scalar(
        select(Department.id).where(
            Department.id == department_id, Department.company_id == company_id
        )
    )
    return found is not None
