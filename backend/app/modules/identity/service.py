import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, AuthenticationError, ConflictError, RateLimitedError
from app.core.request_meta import RequestMeta
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.modules.audit.models import ActorType, AuditOutcome
from app.modules.audit.service import record_event
from app.modules.company.models import Company
from app.modules.company.service import get_company_by_slug
from app.modules.identity.models import LoginAttempt, User, UserSession, UserStatus

INVALID_CREDENTIALS = "Invalid email or password."
_TOUCH_INTERVAL = timedelta(seconds=60)

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_new_password(password: str, *, email: str) -> None:
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Use at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"Use at most {PASSWORD_MAX_LENGTH} characters.")
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 3 and local_part in password.lower():
        problems.append("Do not include your email name in the password.")
    if password.strip() != password:
        problems.append("Do not start or end the password with spaces.")
    if problems:
        raise AppError(
            "The new password does not meet the password policy.",
            code="weak_password",
            details=[{"field": "new_password", "message": p} for p in problems],
        )


@dataclass
class LoginResult:
    user: User
    session: UserSession
    token: str


async def _recent_failures(session: AsyncSession, column, value: str, since: datetime) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(column == value, LoginAttempt.succeeded.is_(False), LoginAttempt.created_at >= since)
    )
    return count or 0


async def authenticate(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    meta: RequestMeta,
) -> LoginResult:
    email = normalize_email(email)
    now = utcnow()
    window_start = now - timedelta(minutes=settings.login_window_minutes)
    company = await get_company_by_slug(session, settings.company_slug)
    company_id = company.id if company else None

    email_failures = await _recent_failures(session, LoginAttempt.email, email, window_start)
    ip_failures = (
        await _recent_failures(session, LoginAttempt.ip_address, meta.ip_address, window_start)
        if meta.ip_address
        else 0
    )
    if (
        email_failures >= settings.login_max_failures_per_email
        or ip_failures >= settings.login_max_failures_per_ip
    ):
        await record_event(
            session,
            action="auth.login.throttled",
            outcome=AuditOutcome.DENIED,
            actor_type=ActorType.ANONYMOUS,
            company_id=company_id,
            meta=meta,
            details={"email": email},
        )
        await session.commit()
        retry_after = str(settings.login_window_minutes * 60)
        raise RateLimitedError(
            "Too many failed sign-in attempts. Please wait and try again later.",
            headers={"Retry-After": retry_after},
        )

    user = None
    if company is not None:
        user = await session.scalar(
            select(User).where(User.company_id == company.id, User.email == email)
        )

    password_ok = verify_password(password, user.password_hash if user else None)
    if user is None or not password_ok or not user.is_active:
        reason = (
            "unknown_account"
            if user is None
            else ("invalid_password" if not password_ok else f"account_{user.status}")
        )
        session.add(LoginAttempt(email=email, ip_address=meta.ip_address, succeeded=False))
        await record_event(
            session,
            action="auth.login.failed",
            outcome=AuditOutcome.FAILURE,
            actor_type=ActorType.ANONYMOUS if user is None else ActorType.USER,
            actor_user_id=user.id if user else None,
            company_id=company_id,
            meta=meta,
            details={"email": email, "reason": reason},
        )
        await session.commit()
        raise AuthenticationError(INVALID_CREDENTIALS, code="invalid_credentials")

    if user.password_hash and password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    session.add(LoginAttempt(email=email, ip_address=meta.ip_address, succeeded=True))
    return await start_session(
        session, settings, user=user, meta=meta, action="auth.login.succeeded"
    )


async def start_session(
    session: AsyncSession, settings: Settings, *, user: User, meta: RequestMeta, action: str
) -> LoginResult:
    now = utcnow()
    token = generate_session_token()
    user_session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
    )
    session.add(user_session)
    user.last_login_at = now
    await session.flush()
    await record_event(
        session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=user.id,
        company_id=user.company_id,
        resource_type="session",
        resource_id=user_session.id,
        meta=meta,
    )
    await session.commit()
    return LoginResult(user=user, session=user_session, token=token)


async def resolve_session(
    session: AsyncSession, settings: Settings, token: str | None
) -> tuple[User, UserSession] | None:
    if not token or len(token) > 256:
        return None
    row = await session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == hash_token(token))
    )
    found = row.first()
    if found is None:
        return None
    user_session, user = found
    now = utcnow()
    idle_deadline = user_session.last_seen_at + timedelta(minutes=settings.session_idle_minutes)
    if (
        user_session.revoked_at is not None
        or user_session.expires_at <= now
        or idle_deadline <= now
        or not user.is_active
    ):
        return None
    if now - user_session.last_seen_at >= _TOUCH_INTERVAL:
        user_session.last_seen_at = now
        await session.commit()
    return user, user_session


async def revoke_session(
    session: AsyncSession, user_session: UserSession, *, reason: str, meta: RequestMeta, user: User
) -> None:
    user_session.revoked_at = utcnow()
    user_session.revoked_reason = reason
    await record_event(
        session,
        action="auth.logout",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=user.id,
        company_id=user.company_id,
        resource_type="session",
        resource_id=user_session.id,
        meta=meta,
    )
    await session.commit()


async def revoke_other_sessions(
    session: AsyncSession, user_id: uuid.UUID, *, keep_session_id: uuid.UUID | None, reason: str
) -> int:
    conditions = [UserSession.user_id == user_id, UserSession.revoked_at.is_(None)]
    if keep_session_id is not None:
        conditions.append(UserSession.id != keep_session_id)
    result = await session.execute(
        update(UserSession).where(*conditions).values(revoked_at=utcnow(), revoked_reason=reason)
    )
    return result.rowcount or 0


async def change_password(
    session: AsyncSession,
    *,
    user: User,
    current_session: UserSession,
    current_password: str,
    new_password: str,
    meta: RequestMeta,
) -> None:
    if not verify_password(current_password, user.password_hash):
        await record_event(
            session,
            action="auth.password.change_failed",
            outcome=AuditOutcome.FAILURE,
            actor_user_id=user.id,
            company_id=user.company_id,
            resource_type="user",
            resource_id=user.id,
            meta=meta,
            details={"reason": "invalid_current_password"},
        )
        await session.commit()
        raise AppError("The current password is incorrect.", code="invalid_current_password")
    validate_new_password(new_password, email=user.email)
    if verify_password(new_password, user.password_hash):
        raise AppError("Choose a password different from the current one.", code="password_reused")

    user.password_hash = hash_password(new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    revoked = await revoke_other_sessions(
        session, user.id, keep_session_id=current_session.id, reason="password_changed"
    )
    await record_event(
        session,
        action="auth.password.changed",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=user.id,
        company_id=user.company_id,
        resource_type="user",
        resource_id=user.id,
        meta=meta,
        details={"other_sessions_revoked": revoked},
    )
    await session.commit()


async def reset_password_as_system(
    session: AsyncSession, *, company: Company, email: str, new_password: str, meta: RequestMeta
) -> User:
    """Operator-initiated reset (CLI). Revokes every session of the account."""
    email = normalize_email(email)
    user = await session.scalar(
        select(User).where(User.company_id == company.id, User.email == email)
    )
    if user is None:
        raise AppError("No user with that email exists.", code="user_not_found")
    validate_new_password(new_password, email=email)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = True
    revoked = await revoke_other_sessions(
        session, user.id, keep_session_id=None, reason="password_reset"
    )
    await record_event(
        session,
        action="auth.password.reset",
        outcome=AuditOutcome.SUCCESS,
        actor_type=ActorType.SYSTEM,
        company_id=company.id,
        resource_type="user",
        resource_id=user.id,
        meta=meta,
        details={"via": "cli", "sessions_revoked": revoked},
    )
    await session.commit()
    return user


async def create_user(
    session: AsyncSession,
    *,
    company: Company,
    email: str,
    full_name: str,
    password: str,
) -> User:
    """Create an active user. Callers are responsible for authorization and auditing."""
    email = normalize_email(email)
    validate_new_password(password, email=email)
    existing = await session.scalar(
        select(User.id).where(User.company_id == company.id, User.email == email)
    )
    if existing:
        raise ConflictError("A user with this email already exists.", code="email_taken")
    user = User(
        company_id=company.id,
        email=email,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        password_changed_at=utcnow(),
    )
    session.add(user)
    await session.flush()
    return user


async def purge_expired_records(
    session: AsyncSession,
    *,
    login_attempt_retention_days: int = 30,
    session_retention_days: int = 30,
) -> dict[str, int]:
    """Retention clean-up for authentication data (run on a schedule)."""
    now = utcnow()
    attempts = await session.execute(
        delete(LoginAttempt).where(
            LoginAttempt.created_at < now - timedelta(days=login_attempt_retention_days)
        )
    )
    cutoff = now - timedelta(days=session_retention_days)
    sessions = await session.execute(
        delete(UserSession).where(
            or_(UserSession.expires_at < cutoff, UserSession.revoked_at < cutoff)
        )
    )
    await session.commit()
    return {"login_attempts": attempts.rowcount or 0, "sessions": sessions.rowcount or 0}
