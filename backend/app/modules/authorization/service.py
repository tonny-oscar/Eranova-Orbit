import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.request_meta import RequestMeta
from app.modules.audit.models import ActorType, AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.catalogue import (
    PERMISSION_CATALOGUE,
    STARTER_ROLES,
    SUPER_ADMIN_SLUG,
    ScopeType,
)
from app.modules.authorization.models import Permission, Role, RolePermission, UserRole
from app.modules.authorization.policy import Grant, Principal, can_delegate
from app.modules.company.models import Company
from app.modules.identity.models import User, UserStatus

logger = logging.getLogger(__name__)

# Scope types whose target tables exist register a validator here. Until the
# products/departments/projects modules land, those scopes cannot be assigned.
ScopeValidator = Callable[[AsyncSession, uuid.UUID, uuid.UUID], Awaitable[bool]]
SCOPE_VALIDATORS: dict[ScopeType, ScopeValidator] = {}


async def load_principal(session: AsyncSession, user: User) -> Principal:
    rows = await session.execute(
        select(Permission.key, UserRole.scope_type, UserRole.scope_id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(UserRole.user_id == user.id, Role.company_id == user.company_id)
    )
    grants: dict[str, set[Grant]] = defaultdict(set)
    for key, scope_type, scope_id in rows:
        grants[key].add(Grant(ScopeType(scope_type), scope_id))
    return Principal(user_id=user.id, company_id=user.company_id, grants=grants)


# ---------------------------------------------------------------------------
# Bootstrap (idempotent)
# ---------------------------------------------------------------------------


async def sync_permission_catalogue(session: AsyncSession) -> dict[str, Permission]:
    existing = {p.key: p for p in await session.scalars(select(Permission))}
    for definition in PERMISSION_CATALOGUE:
        permission = existing.get(definition.key)
        if permission is None:
            permission = Permission(key=definition.key)
            session.add(permission)
            existing[definition.key] = permission
        permission.resource = definition.resource
        permission.action = definition.action
        permission.description = definition.description
        permission.is_sensitive = definition.is_sensitive
    stale = set(existing) - {d.key for d in PERMISSION_CATALOGUE}
    if stale:
        logger.warning(
            "Permissions in database but not in catalogue", extra={"keys": sorted(stale)}
        )
    await session.flush()
    return existing


async def ensure_starter_roles(
    session: AsyncSession, company: Company, permissions: dict[str, Permission]
) -> dict[str, Role]:
    roles = {
        r.slug: r for r in await session.scalars(select(Role).where(Role.company_id == company.id))
    }
    for starter in STARTER_ROLES:
        role = roles.get(starter.slug)
        created = role is None
        if role is None:
            role = Role(
                company_id=company.id,
                slug=starter.slug,
                name=starter.name,
                description=starter.description,
                is_system=True,
                is_locked=starter.locked,
            )
            session.add(role)
            await session.flush()
            roles[starter.slug] = role
        if created or starter.locked:
            current = set(
                await session.scalars(
                    select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
                )
            )
            for key in starter.permissions:
                permission_id = permissions[key].id
                if permission_id not in current:
                    session.add(RolePermission(role_id=role.id, permission_id=permission_id))
    await session.flush()
    return roles


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


async def list_permissions(session: AsyncSession) -> list[Permission]:
    return list(
        await session.scalars(select(Permission).order_by(Permission.resource, Permission.action))
    )


@dataclass
class RoleView:
    role: Role
    permission_keys: list[str]
    assignment_count: int


async def _role_permission_keys(session: AsyncSession, role_ids: list[uuid.UUID]) -> dict:
    keys: dict[uuid.UUID, list[str]] = defaultdict(list)
    if not role_ids:
        return keys
    rows = await session.execute(
        select(RolePermission.role_id, Permission.key)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id.in_(role_ids))
        .order_by(Permission.key)
    )
    for role_id, key in rows:
        keys[role_id].append(key)
    return keys


async def list_roles(session: AsyncSession, company_id: uuid.UUID) -> list[RoleView]:
    roles = list(
        await session.scalars(
            select(Role)
            .where(Role.company_id == company_id)
            .order_by(Role.is_system.desc(), Role.name)
        )
    )
    role_ids = [r.id for r in roles]
    keys = await _role_permission_keys(session, role_ids)
    counts = (
        dict(
            (
                await session.execute(
                    select(UserRole.role_id, func.count())
                    .where(UserRole.role_id.in_(role_ids))
                    .group_by(UserRole.role_id)
                )
            ).all()
        )
        if role_ids
        else {}
    )
    return [RoleView(r, keys.get(r.id, []), counts.get(r.id, 0)) for r in roles]


async def get_role(session: AsyncSession, company_id: uuid.UUID, role_id: uuid.UUID) -> RoleView:
    role = await session.scalar(
        select(Role).where(Role.id == role_id, Role.company_id == company_id)
    )
    if role is None:
        raise NotFoundError("Role not found.")
    keys = await _role_permission_keys(session, [role.id])
    count = await session.scalar(select(func.count()).where(UserRole.role_id == role.id))
    return RoleView(role, keys.get(role.id, []), count or 0)


@dataclass
class AssignmentView:
    assignment: UserRole
    role: Role


async def list_user_assignments(session: AsyncSession, user_id: uuid.UUID) -> list[AssignmentView]:
    rows = await session.execute(
        select(UserRole, Role)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.name, UserRole.created_at)
    )
    return [AssignmentView(a, r) for a, r in rows]


# ---------------------------------------------------------------------------
# Role assignment
# ---------------------------------------------------------------------------


async def _get_company_user(
    session: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID
) -> User:
    user = await session.scalar(
        select(User).where(User.id == user_id, User.company_id == company_id)
    )
    if user is None:
        raise NotFoundError("User not found.")
    return user


async def _active_super_admin_count(session: AsyncSession, company_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count(func.distinct(UserRole.user_id)))
        .join(Role, Role.id == UserRole.role_id)
        .join(User, User.id == UserRole.user_id)
        .where(
            Role.company_id == company_id,
            Role.slug == SUPER_ADMIN_SLUG,
            UserRole.scope_type == ScopeType.COMPANY,
            User.status == UserStatus.ACTIVE,
        )
    )
    return count or 0


async def _ensure_can_delegate(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    role: Role,
    scope: Grant,
    action: str,
    target_user_id: uuid.UUID,
    meta: RequestMeta,
) -> None:
    role_keys = set((await _role_permission_keys(session, [role.id])).get(role.id, []))
    missing = can_delegate(principal, role_keys, scope)
    if missing:
        await record_event(
            session,
            action=action,
            outcome=AuditOutcome.DENIED,
            actor_user_id=actor.id,
            company_id=actor.company_id,
            resource_type="user",
            resource_id=target_user_id,
            meta=meta,
            details={
                "role": role.slug,
                "scope_type": scope.scope_type,
                "scope_id": str(scope.scope_id) if scope.scope_id else None,
                "reason": "exceeds_actor_authority",
                "missing_permission_count": len(missing),
            },
        )
        await session.commit()
        raise PermissionDeniedError(
            "You can only manage roles whose permissions you hold at the same or broader scope.",
            code="role_exceeds_authority",
        )


async def assign_role(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    target_user_id: uuid.UUID,
    role_id: uuid.UUID,
    scope_type: ScopeType,
    scope_id: uuid.UUID | None,
    meta: RequestMeta,
) -> AssignmentView:
    if target_user_id == actor.id:
        raise PermissionDeniedError(
            "Your own role assignments must be changed by another administrator.",
            code="self_role_change",
        )
    target = await _get_company_user(session, actor.company_id, target_user_id)
    role = await session.scalar(
        select(Role).where(Role.id == role_id, Role.company_id == actor.company_id)
    )
    if role is None:
        raise NotFoundError("Role not found.")

    if scope_type in (ScopeType.COMPANY, ScopeType.OWN):
        if scope_id is not None:
            raise AppError("This scope type does not take a scope ID.", code="invalid_scope")
    else:
        if scope_id is None:
            raise AppError("This scope type requires a scope ID.", code="invalid_scope")
        validator = SCOPE_VALIDATORS.get(scope_type)
        if validator is None:
            raise AppError(
                f"The '{scope_type}' scope becomes available when its module is enabled.",
                code="scope_not_available",
            )
        if not await validator(session, actor.company_id, scope_id):
            raise AppError("The scope target does not exist.", code="invalid_scope")

    scope = Grant(scope_type, scope_id)
    await _ensure_can_delegate(
        session,
        actor=actor,
        principal=principal,
        role=role,
        scope=scope,
        action="role.assignment.create",
        target_user_id=target.id,
        meta=meta,
    )

    duplicate = await session.scalar(
        select(UserRole.id).where(
            UserRole.user_id == target.id,
            UserRole.role_id == role.id,
            UserRole.scope_type == scope_type,
            UserRole.scope_id.is_(None) if scope_id is None else UserRole.scope_id == scope_id,
        )
    )
    if duplicate:
        raise ConflictError(
            "The user already has this role at this scope.", code="duplicate_assignment"
        )

    assignment = UserRole(
        user_id=target.id,
        role_id=role.id,
        scope_type=scope_type,
        scope_id=scope_id,
        granted_by_user_id=actor.id,
    )
    session.add(assignment)
    await session.flush()
    await record_event(
        session,
        action="role.assignment.create",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="user",
        resource_id=target.id,
        meta=meta,
        details={
            "assignment_id": str(assignment.id),
            "role": role.slug,
            "scope_type": scope_type,
            "scope_id": str(scope_id) if scope_id else None,
        },
    )
    await session.commit()
    await session.refresh(assignment)
    return AssignmentView(assignment, role)


async def revoke_role(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    target_user_id: uuid.UUID,
    assignment_id: uuid.UUID,
    meta: RequestMeta,
) -> None:
    if target_user_id == actor.id:
        raise PermissionDeniedError(
            "Your own role assignments must be changed by another administrator.",
            code="self_role_change",
        )
    target = await _get_company_user(session, actor.company_id, target_user_id)
    row = (
        await session.execute(
            select(UserRole, Role)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.id == assignment_id, UserRole.user_id == target.id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Role assignment not found.")
    assignment, role = row

    scope = Grant(ScopeType(assignment.scope_type), assignment.scope_id)
    await _ensure_can_delegate(
        session,
        actor=actor,
        principal=principal,
        role=role,
        scope=scope,
        action="role.assignment.delete",
        target_user_id=target.id,
        meta=meta,
    )

    if (
        role.slug == SUPER_ADMIN_SLUG
        and assignment.scope_type == ScopeType.COMPANY
        and target.is_active
        and await _active_super_admin_count(session, actor.company_id) <= 1
    ):
        raise ConflictError(
            "The last active Super Admin cannot be removed.", code="last_super_admin"
        )

    await session.delete(assignment)
    await record_event(
        session,
        action="role.assignment.delete",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="user",
        resource_id=target.id,
        meta=meta,
        details={
            "assignment_id": str(assignment_id),
            "role": role.slug,
            "scope_type": assignment.scope_type,
            "scope_id": str(assignment.scope_id) if assignment.scope_id else None,
        },
    )
    await session.commit()


async def grant_super_admin(
    session: AsyncSession, *, company: Company, user: User, meta: RequestMeta
) -> None:
    """Bootstrap-only path used by the CLI; bypasses delegation checks by design."""
    role = await session.scalar(
        select(Role).where(Role.company_id == company.id, Role.slug == SUPER_ADMIN_SLUG)
    )
    if role is None:
        raise AppError(
            "Run bootstrap before creating the first Super Admin.", code="not_bootstrapped"
        )
    session.add(UserRole(user_id=user.id, role_id=role.id, scope_type=ScopeType.COMPANY))
    await session.flush()
    await record_event(
        session,
        action="role.assignment.create",
        outcome=AuditOutcome.SUCCESS,
        actor_type=ActorType.SYSTEM,
        company_id=company.id,
        resource_type="user",
        resource_id=user.id,
        meta=meta,
        details={"role": role.slug, "scope_type": ScopeType.COMPANY, "via": "cli"},
    )
