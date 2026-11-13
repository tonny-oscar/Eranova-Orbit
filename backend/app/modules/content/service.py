import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.core.request_meta import RequestMeta
from app.db.base import utc_now
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed
from app.modules.content.models import PAGE_SLUGS, ContentPage
from app.modules.content.schemas import PageDraftUpdate, PageVersion, Section
from app.modules.identity.models import User


def _ensure_known(slug: str) -> None:
    if slug not in PAGE_SLUGS:
        raise NotFoundError("Page not found.")


def _company_wide(principal: Principal, permission: str) -> bool:
    return is_allowed(principal, permission, ResourceContext(company_id=principal.company_id))


def draft_of(page: ContentPage | None, slug: str) -> PageVersion:
    if page is None:
        return PageVersion(title=PAGE_SLUGS[slug], summary="", sections=[], seo_description="")
    return PageVersion(
        title=page.draft_title or PAGE_SLUGS[slug],
        summary=page.draft_summary,
        sections=[Section(**s) for s in page.draft_sections],
        seo_description=page.draft_seo_description,
    )


def published_of(page: ContentPage | None) -> PageVersion | None:
    if page is None or page.published_at is None:
        return None
    return PageVersion(
        title=page.published_title or "",
        summary=page.published_summary or "",
        sections=[Section(**s) for s in page.published_sections or []],
        seo_description=page.published_seo_description or "",
    )


def has_unpublished_changes(page: ContentPage | None) -> bool:
    if page is None:
        return False
    published = published_of(page)
    return published is None or published != draft_of(page, page.slug)


async def get_page(session: AsyncSession, company_id: uuid.UUID, slug: str) -> ContentPage | None:
    _ensure_known(slug)
    return await session.scalar(
        select(ContentPage).where(ContentPage.company_id == company_id, ContentPage.slug == slug)
    )


async def list_pages(
    session: AsyncSession, company_id: uuid.UUID
) -> list[tuple[str, ContentPage | None]]:
    pages = {
        p.slug: p
        for p in await session.scalars(
            select(ContentPage).where(ContentPage.company_id == company_id)
        )
    }
    return [(slug, pages.get(slug)) for slug in PAGE_SLUGS]


async def save_draft(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    slug: str,
    payload: PageDraftUpdate,
    meta: RequestMeta,
) -> ContentPage:
    if not _company_wide(principal, "content.update"):
        raise PermissionDeniedError("You cannot edit website content.")
    page = await get_page(session, actor.company_id, slug)
    if page is None:
        page = ContentPage(company_id=actor.company_id, slug=slug)
        session.add(page)
    page.draft_title = payload.title.strip()
    page.draft_summary = payload.summary.strip()
    page.draft_sections = [
        s.model_dump() for s in payload.sections if s.heading.strip() or s.body.strip()
    ]
    page.draft_seo_description = payload.seo_description.strip()
    page.updated_by_user_id = actor.id
    await session.flush()
    await record_event(
        session,
        action="content.draft.save",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="content_page",
        resource_id=page.id,
        meta=meta,
        details={"slug": slug},
    )
    await session.commit()
    await session.refresh(page)
    return page


async def set_published(
    session: AsyncSession,
    *,
    actor: User,
    principal: Principal,
    slug: str,
    published: bool,
    meta: RequestMeta,
) -> ContentPage:
    if not _company_wide(principal, "content.approve"):
        raise PermissionDeniedError("Publishing website content requires approval rights.")
    page = await get_page(session, actor.company_id, slug)
    if published:
        if page is None or not (
            page.draft_title.strip() and (page.draft_sections or page.draft_summary)
        ):
            raise AppError(
                "Add a title and some content before publishing.", code="not_publishable"
            )
        page.published_title = page.draft_title
        page.published_summary = page.draft_summary
        page.published_sections = list(page.draft_sections)
        page.published_seo_description = page.draft_seo_description
        page.published_at = utc_now()
        page.published_by_user_id = actor.id
    else:
        if page is None or page.published_at is None:
            raise AppError("This page is not published.", code="not_published")
        page.published_at = None
    await record_event(
        session,
        action="content.publish" if published else "content.unpublish",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="content_page",
        resource_id=page.id,
        meta=meta,
        details={"slug": slug},
    )
    await session.commit()
    await session.refresh(page)
    return page
