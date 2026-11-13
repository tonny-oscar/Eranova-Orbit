"""Unauthenticated marketplace API.

Only published, confirmed content is exposed, through dedicated public
schemas that never include internal fields (owners, repositories, notes).
"""

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_request_meta
from app.core.config import Settings, get_settings
from app.core.errors import AppError, NotFoundError
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.company.service import get_company_by_slug
from app.modules.content import service as content_service
from app.modules.content.models import PAGE_SLUGS
from app.modules.content.schemas import PublicPage
from app.modules.crm import service as crm_service
from app.modules.crm.schemas import EnquiryAccepted, EnquiryIn
from app.modules.products import service as product_service
from app.modules.products.models import Product
from app.modules.products.schemas import PublicProduct

router = APIRouter(prefix="/public", tags=["public"])

_CACHE = "public, max-age=60"


class SiteInfo(BaseModel):
    company_name: str
    published_pages: list[str]
    categories: list[str]
    privacy_notice_version: str


async def _company_id(db: AsyncSession, settings: Settings):
    company = await get_company_by_slug(db, settings.company_slug)
    if company is None:
        raise AppError("The site is not configured yet.", code="not_configured")
    return company


def _public(product: Product) -> PublicProduct:
    return PublicProduct.model_validate(product, from_attributes=True)


@router.get("/site", response_model=SiteInfo)
async def site_info(
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SiteInfo:
    company = await _company_id(db, settings)
    pages = await content_service.list_pages(db, company.id)
    products = await product_service.list_public_products(db, company.id, q=None, category=None)
    response.headers["Cache-Control"] = _CACHE
    return SiteInfo(
        company_name=company.name,
        published_pages=[slug for slug, page in pages if page and page.published_at],
        categories=sorted({p.category for p in products if p.category}),
        privacy_notice_version=crm_service.PRIVACY_NOTICE_VERSION,
    )


@router.get("/products", response_model=list[PublicProduct])
async def public_products(
    response: Response,
    q: str | None = Query(None, max_length=100),
    category: str | None = Query(None, max_length=60),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[PublicProduct]:
    company = await _company_id(db, settings)
    products = await product_service.list_public_products(db, company.id, q=q, category=category)
    response.headers["Cache-Control"] = _CACHE
    return [_public(p) for p in products]


@router.get("/products/{slug}", response_model=PublicProduct)
async def public_product(
    slug: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PublicProduct:
    company = await _company_id(db, settings)
    product = await product_service.get_public_product(db, company.id, slug)
    response.headers["Cache-Control"] = _CACHE
    return _public(product)


@router.get("/pages/{slug}", response_model=PublicPage)
async def public_page(
    slug: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PublicPage:
    if slug not in PAGE_SLUGS:
        raise NotFoundError("Page not found.")
    company = await _company_id(db, settings)
    page = await content_service.get_page(db, company.id, slug)
    published = content_service.published_of(page)
    if page is None or published is None or page.published_at is None:
        raise NotFoundError("Page not found.")
    response.headers["Cache-Control"] = _CACHE
    return PublicPage(slug=slug, published_at=page.published_at, **published.model_dump())


@router.post("/enquiries", response_model=EnquiryAccepted, status_code=status.HTTP_202_ACCEPTED)
async def submit_enquiry(
    payload: EnquiryIn,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    meta: RequestMeta = Depends(get_request_meta),
) -> EnquiryAccepted:
    await crm_service.submit_enquiry(db, settings, payload, meta)
    return EnquiryAccepted()
