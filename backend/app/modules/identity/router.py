from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_request_meta
from app.core.config import Settings, get_settings
from app.core.request_meta import RequestMeta
from app.core.security import derive_csrf_token
from app.db.session import get_db
from app.modules.authorization.policy import Principal
from app.modules.authorization.service import list_user_assignments, load_principal
from app.modules.company.models import Company
from app.modules.identity import service
from app.modules.identity.models import User, UserSession
from app.modules.identity.schemas import (
    ChangePasswordRequest,
    CompanySummary,
    LoginRequest,
    MeResponse,
    RoleAssignmentSummary,
    UserSummary,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.effective_cookie_name,
        value=token,
        max_age=settings.session_absolute_hours * 3600,
        path="/",
        domain=settings.session_cookie_domain,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.effective_cookie_name,
        path="/",
        domain=settings.session_cookie_domain,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


async def _build_me(
    db: AsyncSession,
    settings: Settings,
    *,
    user: User,
    user_session: UserSession,
    token: str,
    principal: Principal,
) -> MeResponse:
    company = await db.get(Company, user.company_id)
    assignments = await list_user_assignments(db, user.id)
    return MeResponse(
        user=UserSummary.model_validate(user),
        company=CompanySummary.model_validate(company),
        permissions=sorted(principal.permission_keys),
        roles=[
            RoleAssignmentSummary(
                assignment_id=a.assignment.id,
                role_id=a.role.id,
                role_slug=a.role.slug,
                role_name=a.role.name,
                scope_type=a.assignment.scope_type,
                scope_id=a.assignment.scope_id,
            )
            for a in assignments
        ],
        csrf_token=derive_csrf_token(token, settings.secret_key),
        session_expires_at=user_session.expires_at,
    )


@router.post("/login", response_model=MeResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    meta: RequestMeta = Depends(get_request_meta),
) -> MeResponse:
    result = await service.authenticate(
        db, settings, email=payload.email, password=payload.password, meta=meta
    )
    _set_session_cookie(response, settings, result.token)
    principal = await load_principal(db, result.user)
    return await _build_me(
        db,
        settings,
        user=result.user,
        user_session=result.session,
        token=result.token,
        principal=principal,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.revoke_session(db, auth.session, reason="logout", meta=meta, user=auth.user)
    _clear_session_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
async def me(
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MeResponse:
    return await _build_me(
        db,
        settings,
        user=auth.user,
        user_session=auth.session,
        token=auth.token,
        principal=auth.principal,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.change_password(
        db,
        user=auth.user,
        current_session=auth.session,
        current_password=payload.current_password,
        new_password=payload.new_password,
        meta=meta,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
