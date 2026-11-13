import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.api.pagination import Page, PageParams, page_params
from app.core.errors import AppError
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.documents import service
from app.modules.documents.service import (
    MAX_UPLOAD_BYTES,
    DocumentDetail,
    DocumentMeta,
    DocumentOut,
    DocumentPatch,
    MembersIn,
)

router = APIRouter(prefix="/documents", tags=["documents"])


async def _read_limited(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError("Files must be 10 MB or smaller.", code="file_too_large")
    return data


def _optional_uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


@router.get("", response_model=Page[DocumentOut])
async def list_documents(
    q: str | None = Query(None, max_length=100),
    category: str | None = Query(None, max_length=20),
    product_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    page: PageParams = Depends(page_params),
    auth: AuthContext = Depends(require_permission("document.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[DocumentOut]:
    rows, total = await service.list_documents(
        db,
        auth.principal,
        q=q,
        category=category,
        product_id=product_id,
        project_id=project_id,
        limit=page.limit,
        offset=page.offset,
    )
    items = await service.outs(db, auth.principal, rows)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("", response_model=DocumentDetail, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    category: Annotated[str, Form()] = "other",
    description: Annotated[str, Form()] = "",
    visibility: Annotated[str, Form()] = "scoped",
    product_id: Annotated[str | None, Form()] = None,
    department_id: Annotated[str | None, Form()] = None,
    project_id: Annotated[str | None, Form()] = None,
    auth: AuthContext = Depends(require_permission("document.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> DocumentDetail:
    try:
        meta_in = DocumentMeta(
            title=title,
            category=category,
            description=description,
            visibility=visibility,
            product_id=_optional_uuid(product_id),
            department_id=_optional_uuid(department_id),
            project_id=_optional_uuid(project_id),
        )
    except (ValidationError, ValueError) as exc:
        raise AppError(
            "Check the document details and try again.", code="validation_error"
        ) from exc
    data = await _read_limited(file)
    d = await service.upload(
        db, auth.user, auth.principal, meta_in, file.filename or "", data, meta
    )
    return await service.detail(db, auth.principal, d)


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("document.read")),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetail:
    d = await service.get_document(db, auth.principal, document_id)
    return await service.detail(db, auth.principal, d)


@router.patch("/{document_id}", response_model=DocumentDetail)
async def update_document(
    document_id: uuid.UUID,
    payload: DocumentPatch,
    auth: AuthContext = Depends(require_permission("document.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> DocumentDetail:
    d = await service.update(db, auth.user, auth.principal, document_id, payload, meta)
    return await service.detail(db, auth.principal, d)


@router.post("/{document_id}/versions", response_model=DocumentDetail, status_code=201)
async def add_version(
    document_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    note: Annotated[str | None, Form(max_length=500)] = None,
    auth: AuthContext = Depends(require_permission("document.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> DocumentDetail:
    data = await _read_limited(file)
    d = await service.add_version(
        db, auth.user, auth.principal, document_id, file.filename or "", data, note, meta
    )
    return await service.detail(db, auth.principal, d)


@router.put("/{document_id}/members", response_model=DocumentDetail)
async def set_members(
    document_id: uuid.UUID,
    payload: MembersIn,
    auth: AuthContext = Depends(require_permission("document.update")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> DocumentDetail:
    d = await service.set_members(db, auth.user, auth.principal, document_id, payload, meta)
    return await service.detail(db, auth.principal, d)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("document.delete")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.delete(db, auth.user, auth.principal, document_id, meta)
    return Response(status_code=204)


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    version: int | None = Query(None, ge=1),
    auth: AuthContext = Depends(require_permission("document.read")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    v, data = await service.download(db, auth.user, auth.principal, document_id, version, meta)
    ascii_name = v.filename.encode("ascii", "ignore").decode() or "download"
    return Response(
        content=data,
        media_type=v.content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(v.filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )
