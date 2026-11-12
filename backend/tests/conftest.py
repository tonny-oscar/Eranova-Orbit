import os

# Settings must be in place before any app module reads them.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://orbit:orbit_local_only@localhost:5433/orbit_test"
)
os.environ["SECRET_KEY"] = "test-secret-key-for-automated-tests-only-0123456789"
os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:5173"
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ.setdefault("LOG_LEVEL", "WARNING")

from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import dispose_engine, get_db
from app.main import create_app
from app.modules.authorization.models import Role, UserRole
from app.modules.company.models import Company
from app.modules.identity.models import User
from app.modules.identity.service import create_user

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PASSWORD = "correct-horse-battery-staple"


def alembic_config(connection) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["connection"] = connection
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(lambda sync_conn: command.upgrade(alembic_config(sync_conn), "head"))
    yield engine
    await engine.dispose()
    await dispose_engine()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as conn:
        transaction = await conn.begin()
        yield conn
        await transaction.rollback()


@pytest.fixture
async def db(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """Session whose commits become savepoints inside a per-test transaction."""
    session = AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    yield session
    await session.close()


@pytest.fixture
async def app(db: AsyncSession):
    application = create_app(get_settings())

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def company(db: AsyncSession) -> Company:
    from app.cli import bootstrap

    await bootstrap(db)
    found = await db.scalar(select(Company).where(Company.slug == get_settings().company_slug))
    assert found is not None
    return found


MakeUser = Callable[..., Awaitable[User]]


@pytest.fixture
def make_user(db: AsyncSession, company: Company) -> MakeUser:
    async def _make(
        email: str,
        *,
        role: str | None = None,
        scope_type: str = "company",
        scope_id=None,
        password: str = DEFAULT_PASSWORD,
        full_name: str = "Test User",
    ) -> User:
        user = await create_user(
            db, company=company, email=email, full_name=full_name, password=password
        )
        if role:
            role_row = await db.scalar(
                select(Role).where(Role.company_id == company.id, Role.slug == role)
            )
            assert role_row is not None, f"unknown role {role}"
            db.add(
                UserRole(
                    user_id=user.id, role_id=role_row.id, scope_type=scope_type, scope_id=scope_id
                )
            )
        await db.commit()
        return user

    return _make


async def login(client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD) -> str:
    """Sign in and return the CSRF token for subsequent unsafe requests."""
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]
