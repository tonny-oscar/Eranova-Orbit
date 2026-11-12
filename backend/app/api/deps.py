from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.request_meta import RequestMeta, request_meta
from app.core.security import csrf_token_matches
from app.db.session import get_db
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.catalogue import PERMISSION_CATALOGUE, PERMISSION_KEYS
from app.modules.authorization.policy import Principal, is_allowed
from app.modules.authorization.service import load_principal
from app.modules.identity.models import User, UserSession
from app.modules.identity.service import resolve_session

CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_SENSITIVE_PERMISSIONS = frozenset(p.key for p in PERMISSION_CATALOGUE if p.is_sensitive)


@dataclass
class AuthContext:
    user: User
    session: UserSession
    principal: Principal
    token: str


def session_token_from(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.effective_cookie_name)


async def get_auth_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    token = session_token_from(request, settings)
    resolved = await resolve_session(db, settings, token)
    if resolved is None or token is None:
        raise AuthenticationError("Sign in to continue.")
    user, user_session = resolved
    if request.method not in _SAFE_METHODS and not csrf_token_matches(
        request.headers.get(CSRF_HEADER), token, settings.secret_key
    ):
        raise PermissionDeniedError("Missing or invalid CSRF token.", code="csrf_failed")
    principal = await load_principal(db, user)
    return AuthContext(user=user, session=user_session, principal=principal, token=token)


def require_permission(permission: str) -> Callable[..., Awaitable[AuthContext]]:
    """Route dependency enforcing that the caller holds ``permission`` at some scope.

    Record-level checks (``is_allowed`` with a ``ResourceContext``) and
    scope-filtered queries remain the responsibility of each service.
    """
    if permission not in PERMISSION_KEYS:
        raise ValueError(f"Unknown permission: {permission}")

    async def dependency(
        request: Request,
        auth: AuthContext = Depends(get_auth_context),
        db: AsyncSession = Depends(get_db),
    ) -> AuthContext:
        if is_allowed(auth.principal, permission):
            return auth
        if permission in _SENSITIVE_PERMISSIONS:
            await record_event(
                db,
                action="authz.denied",
                outcome=AuditOutcome.DENIED,
                actor_user_id=auth.user.id,
                company_id=auth.user.company_id,
                meta=request_meta(request),
                details={"permission": permission, "path": request.url.path},
            )
            await db.commit()
        raise PermissionDeniedError("You do not have permission to perform this action.")

    return dependency


def get_request_meta(request: Request) -> RequestMeta:
    return request_meta(request)
