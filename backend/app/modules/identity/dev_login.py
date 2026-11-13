"""Local-development sign-in bypass.

Only reachable when ENVIRONMENT=local and DEV_AUTO_LOGIN=true (Settings refuses
the flag anywhere else). Signs the browser in as the first active Super Admin,
creating a local developer account on a fresh database.
"""

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core.request_meta import SYSTEM_META, RequestMeta
from app.modules.authorization.catalogue import SUPER_ADMIN_SLUG, ScopeType
from app.modules.authorization.models import Role, UserRole
from app.modules.authorization.service import (
    ensure_starter_roles,
    grant_super_admin,
    sync_permission_catalogue,
)
from app.modules.company.service import ensure_company
from app.modules.identity.models import User, UserStatus
from app.modules.identity.service import LoginResult, create_user, start_session

DEV_EMAIL = "developer@eranova.local"


def is_enabled(settings: Settings) -> bool:
    return settings.environment == "local" and settings.dev_auto_login


async def dev_login(session: AsyncSession, settings: Settings, meta: RequestMeta) -> LoginResult:
    if not is_enabled(settings):
        raise NotFoundError("Not found.")
    company = await ensure_company(session, settings)
    user = await session.scalar(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.company_id == company.id,
            User.status == UserStatus.ACTIVE,
            Role.slug == SUPER_ADMIN_SLUG,
            UserRole.scope_type == ScopeType.COMPANY,
        )
        .order_by(User.created_at)
        .limit(1)
    )
    if user is None:
        permissions = await sync_permission_catalogue(session)
        await ensure_starter_roles(session, company, permissions)
        user = await session.scalar(select(User).where(User.email == DEV_EMAIL))
        if user is None:
            user = await create_user(
                session,
                company=company,
                email=DEV_EMAIL,
                full_name="Local Developer",
                password=secrets.token_urlsafe(24),
            )
        await grant_super_admin(session, company=company, user=user, meta=SYSTEM_META)
    return await start_session(session, settings, user=user, meta=meta, action="auth.dev_login")
