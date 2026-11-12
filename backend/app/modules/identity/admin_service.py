"""Administrator operations on user accounts.

Guard: an administrator may only act on accounts whose permissions they
already hold company-wide. This stops a delegated admin from resetting a
Super Admin's password or disabling a more privileged account.
"""

import secrets
import string
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.request_meta import RequestMeta
from app.core.security import hash_password
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.catalogue import ScopeType
from app.modules.authorization.policy import (
    Grant,
    Principal,
    ResourceContext,
    can_delegate,
    is_allowed,
)
from app.modules.authorization.service import (
    active_super_admin_count,
    is_super_admin,
    load_principal,
)
from app.modules.company.models import Company
from app.modules.identity.models import User, UserStatus
from app.modules.identity.service import (
    create_user,
    revoke_other_sessions,
    utcnow,
    validate_new_password,
)

_ALPHABET = string.ascii_letters + string.digits


def generate_temporary_password(email: str) -> str:
    while True:
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(16))
        try:
            validate_new_password(candidate, email=email)
        except AppError:
            continue
        return candidate


def _require_company_permission(principal: Principal, permission: str, message: str) -> None:
    if not is_allowed(principal, permission, ResourceContext(company_id=principal.company_id)):
        raise PermissionDeniedError(message)


async def _get_user(session: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User).where(User.id == user_id, User.company_id == company_id)
    )
    if user is None:
        raise NotFoundError("User not found.")
    return user


async def _ensure_can_act_on(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    target: User,
    action: str,
    meta: RequestMeta,
) -> None:
    if target.id == actor.id:
        raise PermissionDeniedError(
            "Use your own settings page to change your account.", code="self_admin_action"
        )
    target_principal = await load_principal(session, target)
    missing = can_delegate(principal, target_principal.permission_keys, Grant(ScopeType.COMPANY))
    if missing:
        await record_event(
            session,
            action=action,
            outcome=AuditOutcome.DENIED,
            actor_user_id=actor.id,
            company_id=actor.company_id,
            resource_type="user",
            resource_id=target.id,
            meta=meta,
            details={"reason": "target_more_privileged", "missing_permission_count": len(missing)},
        )
        await session.commit()
        raise PermissionDeniedError(
            "This account has access you do not hold, so you cannot manage it.",
            code="target_more_privileged",
        )


@dataclass
class CreatedUser:
    user: User
    temporary_password: str


async def create_user_by_admin(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    company: Company,
    email: str,
    full_name: str,
    meta: RequestMeta,
) -> CreatedUser:
    _require_company_permission(
        principal, "user.create", "Creating users requires company-wide access."
    )
    temporary = generate_temporary_password(email)
    user = await create_user(
        session, company=company, email=email, full_name=full_name, password=temporary
    )
    user.must_change_password = True
    await record_event(
        session,
        action="user.create",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="user",
        resource_id=user.id,
        meta=meta,
        details={"email": user.email},
    )
    await session.commit()
    await session.refresh(user)
    return CreatedUser(user=user, temporary_password=temporary)


async def update_user(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    user_id: uuid.UUID,
    full_name: str | None,
    status: UserStatus | None,
    meta: RequestMeta,
) -> User:
    target = await _get_user(session, actor.company_id, user_id)
    changes: dict[str, dict[str, str]] = {}

    if full_name is not None and full_name.strip() != target.full_name:
        if target.id != actor.id:
            _require_company_permission(principal, "user.update", "You cannot edit other users.")
        changes["full_name"] = {"from": target.full_name, "to": full_name.strip()}
        target.full_name = full_name.strip()

    if status is not None and status != target.status:
        _require_company_permission(
            principal, "user.manage", "Changing account status requires user management access."
        )
        if status == UserStatus.INVITED:
            raise AppError("Accounts can only be activated or disabled.", code="invalid_status")
        await _ensure_can_act_on(
            session,
            actor=actor,
            principal=principal,
            target=target,
            action="user.status.change",
            meta=meta,
        )
        if (
            status == UserStatus.DISABLED
            and await is_super_admin(session, target)
            and await active_super_admin_count(session, actor.company_id) <= 1
        ):
            raise ConflictError(
                "The last active Super Admin cannot be disabled.", code="last_super_admin"
            )
        changes["status"] = {"from": target.status, "to": status}
        target.status = status
        if status == UserStatus.DISABLED:
            await revoke_other_sessions(session, target.id, keep_session_id=None, reason="disabled")

    if changes:
        await record_event(
            session,
            action="user.update",
            outcome=AuditOutcome.SUCCESS,
            actor_user_id=actor.id,
            company_id=actor.company_id,
            resource_type="user",
            resource_id=target.id,
            meta=meta,
            details={"changes": changes},
        )
        await session.commit()
        await session.refresh(target)
    return target


async def reset_password_by_admin(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    user_id: uuid.UUID,
    meta: RequestMeta,
) -> str:
    _require_company_permission(
        principal, "user.manage", "Resetting passwords requires user management access."
    )
    target = await _get_user(session, actor.company_id, user_id)
    await _ensure_can_act_on(
        session,
        actor=actor,
        principal=principal,
        target=target,
        action="user.password.reset",
        meta=meta,
    )
    temporary = generate_temporary_password(target.email)
    target.password_hash = hash_password(temporary)
    target.password_changed_at = utcnow()
    target.must_change_password = True
    revoked = await revoke_other_sessions(
        session, target.id, keep_session_id=None, reason="password_reset"
    )
    await record_event(
        session,
        action="user.password.reset",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="user",
        resource_id=target.id,
        meta=meta,
        details={"sessions_revoked": revoked},
    )
    await session.commit()
    return temporary
