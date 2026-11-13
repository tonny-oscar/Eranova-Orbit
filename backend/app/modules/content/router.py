from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.authorization.policy import ResourceContext, is_allowed
from app.modules.content import service
from app.modules.content.models import PAGE_SLUGS, ContentPage
from app.modules.content.schemas import PageAdminOut, PageDraftUpdate, PageListItem

router = APIRouter(prefix="/content/pages", tags=["content"])


def _admin_out(auth: AuthContext, slug: str, page: ContentPage | None) -> PageAdminOut:
    company = ResourceContext(company_id=auth.user.company_id)
    return PageAdminOut(
        slug=slug,
        label=PAGE_SLUGS[slug],
        draft=service.draft_of(page, slug),
        published=service.published_of(page),
        published_at=page.published_at if page else None,
        has_unpublished_changes=service.has_unpublished_changes(page),
        updated_at=page.updated_at if page else None,
        can_edit=is_allowed(auth.principal, "content.update", company),
        can_publish=is_allowed(auth.principal, "content.approve", company),
    )


@router.get("", response_model=list[PageListItem])
async def list_pages(
    auth: AuthContext = Depends(require_permission("content.read")),
    db: AsyncSession = Depends(get_db),
) -> list[PageListItem]:
    return [
        PageListItem(
            slug=slug,
            label=PAGE_SLUGS[slug],
            is_published=bool(page and page.published_at),
            has_unpublished_changes=service.has_unpublished_changes(page),
            published_at=page.published_at if page else None,
            updated_at=page.updated_at if page else None,
        )
        for slug, page in await service.list_pages(db, auth.user.company_id)
    ]


@router.get("/{slug}", response_model=PageAdminOut)
async def get_page(
    slug: str,
    auth: AuthContext = Depends(require_permission("content.read")),
    db: AsyncSession = Depends(get_db),
) -> PageAdminOut:
    page = await service.get_page(db, auth.user.company_id, slug)
    return _admin_out(auth, slug, page)


@router.put("/{slug}", response_model=PageAdminOut)
async def save_draft(
    slug: str,
    payload: PageDraftUpdate,
    auth: AuthContext = Depends(require_permission("content.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> PageAdminOut:
    page = await service.save_draft(
        db, actor=auth.user, principal=auth.principal, slug=slug, payload=payload, meta=meta
    )
    return _admin_out(auth, slug, page)


@router.post("/{slug}/publish", response_model=PageAdminOut)
async def publish(
    slug: str,
    auth: AuthContext = Depends(require_permission("content.approve")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> PageAdminOut:
    page = await service.set_published(
        db, actor=auth.user, principal=auth.principal, slug=slug, published=True, meta=meta
    )
    return _admin_out(auth, slug, page)


@router.post("/{slug}/unpublish", response_model=PageAdminOut)
async def unpublish(
    slug: str,
    auth: AuthContext = Depends(require_permission("content.approve")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> PageAdminOut:
    page = await service.set_published(
        db, actor=auth.user, principal=auth.principal, slug=slug, published=False, meta=meta
    )
    return _admin_out(auth, slug, page)
