"""Operational commands.

python -m app.cli bootstrap            Sync company, permission catalogue and starter roles
python -m app.cli create-superadmin    Interactively create the first Super Admin
python -m app.cli reset-password       Set a new password for a user and sign them out everywhere
python -m app.cli purge-auth-records   Apply retention to login attempts and old sessions
"""

import argparse
import asyncio
import getpass
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.request_meta import SYSTEM_META
from app.db.session import dispose_engine, get_sessionmaker
from app.modules.audit.models import ActorType, AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.service import (
    ensure_starter_roles,
    grant_super_admin,
    sync_permission_catalogue,
)
from app.modules.company.service import ensure_company
from app.modules.identity.service import (
    create_user,
    purge_expired_records,
    reset_password_as_system,
)

COMMANDS = ["bootstrap", "create-superadmin", "reset-password", "purge-auth-records"]


async def bootstrap(session: AsyncSession) -> None:
    settings = get_settings()
    company = await ensure_company(session, settings)
    permissions = await sync_permission_catalogue(session)
    roles = await ensure_starter_roles(session, company, permissions)
    await session.commit()
    print(
        f"Bootstrap complete: company '{company.slug}', "
        f"{len(permissions)} permissions, {len(roles)} roles."
    )


async def _create_superadmin(email: str, full_name: str, password: str) -> None:
    async with get_sessionmaker()() as session:
        settings = get_settings()
        await bootstrap(session)
        company = await ensure_company(session, settings)
        user = await create_user(
            session, company=company, email=email, full_name=full_name, password=password
        )
        await record_event(
            session,
            action="user.create",
            outcome=AuditOutcome.SUCCESS,
            actor_type=ActorType.SYSTEM,
            company_id=company.id,
            resource_type="user",
            resource_id=user.id,
            meta=SYSTEM_META,
            details={"via": "cli", "email": user.email},
        )
        await grant_super_admin(session, company=company, user=user, meta=SYSTEM_META)
        await session.commit()
        print(f"Super Admin created: {user.email}")


def _prompt_email() -> str:
    email = input("Email: ").strip()
    try:
        return validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        sys.exit(f"Invalid email: {exc}")


def _prompt_password() -> str:
    password = getpass.getpass("Password (min 12 characters): ")
    if password != getpass.getpass("Confirm password: "):
        sys.exit("Passwords do not match.")
    return password


def _prompt_superadmin() -> tuple[str, str, str]:
    email = _prompt_email()
    full_name = input("Full name: ").strip()
    if not full_name:
        sys.exit("Full name is required.")
    return email, full_name, _prompt_password()


async def _reset_password(email: str, password: str) -> None:
    async with get_sessionmaker()() as session:
        company = await ensure_company(session, get_settings())
        user = await reset_password_as_system(
            session, company=company, email=email, new_password=password, meta=SYSTEM_META
        )
        print(f"Password reset for {user.email}; all their sessions were signed out.")


async def _run(command: str) -> None:
    try:
        if command == "bootstrap":
            async with get_sessionmaker()() as session:
                await bootstrap(session)
        elif command == "create-superadmin":
            await _create_superadmin(*_prompt_superadmin())
        elif command == "reset-password":
            await _reset_password(_prompt_email(), _prompt_password())
        elif command == "purge-auth-records":
            async with get_sessionmaker()() as session:
                print(await purge_expired_records(session))
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args()
    configure_logging(get_settings().log_level)
    try:
        asyncio.run(_run(args.command))
    except AppError as exc:
        details = "; ".join(d.get("message", "") for d in exc.details)
        sys.exit(f"Error: {exc.message} {details}".strip())


if __name__ == "__main__":
    main()
