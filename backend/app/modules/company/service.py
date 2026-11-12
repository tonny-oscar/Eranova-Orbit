from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.company.models import Company


async def get_company_by_slug(session: AsyncSession, slug: str) -> Company | None:
    return await session.scalar(select(Company).where(Company.slug == slug))


async def ensure_company(session: AsyncSession, settings: Settings) -> Company:
    company = await get_company_by_slug(session, settings.company_slug)
    if company is None:
        company = Company(
            name=settings.company_name,
            slug=settings.company_slug,
            timezone=settings.company_timezone,
        )
        session.add(company)
        await session.flush()
    return company
