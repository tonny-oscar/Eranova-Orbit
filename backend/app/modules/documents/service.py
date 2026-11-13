"""Document centre: permission-checked storage, search, versions and downloads."""

import hashlib
import re
import unicodedata
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, false, func, or_, select, true

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed, scope_filter
from app.modules.crm.service import lookup
from app.modules.documents.models import (
    DOCUMENT_CATEGORIES,
    Document,
    DocumentBlob,
    DocumentMember,
    DocumentVersion,
)
from app.modules.identity.models import User, UserStatus
from app.modules.people.models import Department
from app.modules.people.service import department_exists
from app.modules.products.models import Product
from app.modules.products.service import escape_like, product_exists
from app.modules.work.models import Project
from app.modules.work.service import project_exists

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
Category = Literal[DOCUMENT_CATEGORIES]  # type: ignore[valid-type]

_ZIP = (b"PK\x03\x04",)
_OLE = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)
# extension -> (content type, accepted leading bytes; None means UTF-8 text)
ALLOWED_TYPES: dict[str, tuple[str, tuple[bytes, ...] | None]] = {
    "pdf": ("application/pdf", (b"%PDF-",)),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", _ZIP),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _ZIP),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", _ZIP),
    "odt": ("application/vnd.oasis.opendocument.text", _ZIP),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", _ZIP),
    "odp": ("application/vnd.oasis.opendocument.presentation", _ZIP),
    "doc": ("application/msword", _OLE),
    "xls": ("application/vnd.ms-excel", _OLE),
    "ppt": ("application/vnd.ms-powerpoint", _OLE),
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "webp": ("image/webp", (b"RIFF",)),
    "csv": ("text/csv", None),
    "txt": ("text/plain", None),
    "md": ("text/markdown", None),
}


# --- Schemas ------------------------------------------------------------------------------


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class DocumentMeta(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    category: Category = "other"
    visibility: Literal["scoped", "restricted"] = "scoped"
    product_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


class DocumentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    category: Category | None = None
    visibility: Literal["scoped", "restricted"] | None = None


class MembersIn(BaseModel):
    user_ids: list[uuid.UUID] = Field(max_length=200)


class VersionOut(BaseModel):
    version: int
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    note: str | None
    uploaded_by: Ref | None
    created_at: datetime


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    category: str
    visibility: str
    product: Ref | None
    department: Ref | None
    project: Ref | None
    owner: Ref | None
    current_version: int
    filename: str
    content_type: str
    size_bytes: int
    updated_at: datetime
    can_update: bool = False


class DocumentDetail(DocumentOut):
    versions: list[VersionOut]
    members: list[Ref]
    can_manage_members: bool = False


# --- File validation ------------------------------------------------------------------------


def safe_filename(name: str) -> str:
    name = unicodedata.normalize("NFKC", name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^\w.\- ()]+", "_", name).strip(" .")
    return name[:200] or "file"


def validate_file(filename: str, data: bytes) -> tuple[str, str]:
    """Return (safe filename, content type). The type comes from the checked
    extension and file signature, never from the client's claim."""
    name = safe_filename(filename)
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED_TYPES:
        allowed = ", ".join(sorted(ALLOWED_TYPES))
        raise AppError(f"This file type is not accepted. Allowed: {allowed}.", code="file_type")
    if not data:
        raise AppError("The file is empty.", code="file_empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError("Files must be 10 MB or smaller.", code="file_too_large")
    content_type, signatures = ALLOWED_TYPES[extension]
    if signatures is None:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError("Text files must be UTF-8.", code="file_content") from exc
        if b"\x00" in data:
            raise AppError("The file content does not match its type.", code="file_content")
        content_type += "; charset=utf-8"
    elif not data.startswith(signatures) or (extension == "webp" and data[8:12] != b"WEBP"):
        raise AppError("The file content does not match its type.", code="file_content")
    return name, content_type


# --- Access -------------------------------------------------------------------------------------


def document_context(d: Document) -> ResourceContext:
    return ResourceContext(
        company_id=d.company_id,
        department_id=d.department_id,
        product_ids=frozenset({d.product_id}) if d.product_id else frozenset(),
        project_id=d.project_id,
        owner_user_id=d.owner_user_id,
    )


def _company_manager(principal: Principal) -> bool:
    return is_allowed(
        principal, "document.manage", ResourceContext(company_id=principal.company_id)
    )


def document_scope(principal: Principal) -> ColumnElement[bool]:
    scope = scope_filter(principal, "document.read")
    if scope.company_wide:
        scoped = true()
    else:
        conditions: list[ColumnElement[bool]] = []
        if scope.department_ids:
            conditions.append(Document.department_id.in_(scope.department_ids))
        if scope.product_ids:
            conditions.append(Document.product_id.in_(scope.product_ids))
        if scope.project_ids:
            conditions.append(Document.project_id.in_(scope.project_ids))
        if scope.own:
            conditions.append(Document.owner_user_id == principal.user_id)
        scoped = or_(*conditions) if conditions else false()
    if _company_manager(principal):
        return scoped
    restricted_ok = or_(
        Document.visibility != "restricted",
        Document.owner_user_id == principal.user_id,
        Document.id.in_(
            select(DocumentMember.document_id).where(DocumentMember.user_id == principal.user_id)
        ),
    )
    return scoped & restricted_ok


async def _is_member(session, document_id, user_id) -> bool:
    return bool(
        await session.scalar(
            select(DocumentMember.id).where(
                DocumentMember.document_id == document_id, DocumentMember.user_id == user_id
            )
        )
    )


async def can_read(session, principal: Principal, d: Document) -> bool:
    if d.company_id != principal.company_id:
        return False
    if not is_allowed(principal, "document.read", document_context(d)):
        return False
    if d.visibility != "restricted" or d.owner_user_id == principal.user_id:
        return True
    return _company_manager(principal) or await _is_member(session, d.id, principal.user_id)


async def get_document(session, principal, document_id, permission="document.read") -> Document:
    d = await session.scalar(
        select(Document).where(
            Document.id == document_id, Document.company_id == principal.company_id
        )
    )
    if d is None or not await can_read(session, principal, d):
        raise NotFoundError("Document not found.")
    if permission != "document.read" and not is_allowed(principal, permission, document_context(d)):
        raise PermissionDeniedError("You cannot change this document.")
    return d


async def _audit(session, actor, action, document_id, meta, details=None):
    await record_event(
        session,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=actor.id,
        company_id=actor.company_id,
        resource_type="document",
        resource_id=document_id,
        meta=meta,
        details=details or {},
    )


# --- Queries ------------------------------------------------------------------------------------


async def list_documents(
    session,
    principal,
    *,
    q=None,
    category=None,
    product_id=None,
    project_id=None,
    limit=25,
    offset=0,
):
    conditions = [Document.company_id == principal.company_id, document_scope(principal)]
    if category:
        conditions.append(Document.category == category)
    if product_id:
        conditions.append(Document.product_id == product_id)
    if project_id:
        conditions.append(Document.project_id == project_id)
    if q and q.strip():
        pattern = f"%{escape_like(q.strip().lower())}%"
        conditions.append(
            or_(
                func.lower(Document.title).like(pattern, escape="\\"),
                func.lower(Document.description).like(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(Document).where(*conditions))
    rows = await session.scalars(
        select(Document)
        .where(*conditions)
        .order_by(Document.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def _current_versions(session, docs) -> dict:
    if not docs:
        return {}
    rows = await session.scalars(
        select(DocumentVersion).where(
            or_(
                *[
                    (DocumentVersion.document_id == d.id)
                    & (DocumentVersion.version == d.current_version)
                    for d in docs
                ]
            )
        )
    )
    return {v.document_id: v for v in rows}


async def outs(session, principal, docs: list[Document]) -> list[DocumentOut]:
    versions = await _current_versions(session, docs)
    products = await lookup(session, Product, {d.product_id for d in docs})
    departments = await lookup(session, Department, {d.department_id for d in docs})
    projects = await lookup(session, Project, {d.project_id for d in docs})
    users = await lookup(session, User, {d.owner_user_id for d in docs})
    out = []
    for d in docs:
        v = versions.get(d.id)
        product, dept, project, owner = (
            products.get(d.product_id),
            departments.get(d.department_id),
            projects.get(d.project_id),
            users.get(d.owner_user_id),
        )
        out.append(
            DocumentOut(
                id=d.id,
                title=d.title,
                description=d.description,
                category=d.category,
                visibility=d.visibility,
                product=Ref(id=product.id, name=product.name) if product else None,
                department=Ref(id=dept.id, name=dept.name) if dept else None,
                project=Ref(id=project.id, name=project.name) if project else None,
                owner=Ref(id=owner.id, name=owner.full_name) if owner else None,
                current_version=d.current_version,
                filename=v.filename if v else "",
                content_type=v.content_type if v else "",
                size_bytes=v.size_bytes if v else 0,
                updated_at=d.updated_at,
                can_update=is_allowed(principal, "document.update", document_context(d)),
            )
        )
    return out


async def detail(session, principal, d: Document) -> DocumentDetail:
    base = (await outs(session, principal, [d]))[0]
    versions = list(
        await session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == d.id)
            .order_by(DocumentVersion.version.desc())
        )
    )
    member_ids = list(
        await session.scalars(
            select(DocumentMember.user_id).where(DocumentMember.document_id == d.id)
        )
    )
    users = await lookup(session, User, {v.uploaded_by_user_id for v in versions} | set(member_ids))

    def ref(uid):
        u = users.get(uid)
        return Ref(id=u.id, name=u.full_name) if u else None

    return DocumentDetail(
        **base.model_dump(),
        versions=[
            VersionOut(
                version=v.version,
                filename=v.filename,
                content_type=v.content_type,
                size_bytes=v.size_bytes,
                sha256=v.sha256,
                note=v.note,
                uploaded_by=ref(v.uploaded_by_user_id),
                created_at=v.created_at,
            )
            for v in versions
        ],
        members=[r for r in (ref(uid) for uid in member_ids) if r],
        can_manage_members=base.can_update and d.visibility == "restricted",
    )


# --- Commands -----------------------------------------------------------------------------------


async def _check_links(session, company_id, meta: DocumentMeta):
    if meta.product_id and not await product_exists(session, company_id, meta.product_id):
        raise AppError("Product not found.", code="invalid_product")
    if meta.department_id and not await department_exists(session, company_id, meta.department_id):
        raise AppError("Department not found.", code="invalid_department")
    if meta.project_id and not await project_exists(session, company_id, meta.project_id):
        raise AppError("Project not found.", code="invalid_project")


def _store(session, document_id, version, filename, content_type, data, actor, note=None):
    v = DocumentVersion(
        document_id=document_id,
        version=version,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        note=note,
        uploaded_by_user_id=actor.id,
    )
    session.add(v)
    return v


async def upload(
    session, actor, principal, meta_in: DocumentMeta, filename, data, meta
) -> Document:
    context = ResourceContext(
        company_id=actor.company_id,
        department_id=meta_in.department_id,
        product_ids=frozenset({meta_in.product_id}) if meta_in.product_id else frozenset(),
        project_id=meta_in.project_id,
        owner_user_id=actor.id,
    )
    if not is_allowed(principal, "document.create", context):
        raise PermissionDeniedError("You cannot add documents here.")
    await _check_links(session, actor.company_id, meta_in)
    name, content_type = validate_file(filename, data)
    d = Document(company_id=actor.company_id, owner_user_id=actor.id, **meta_in.model_dump())
    d.title = d.title.strip()
    session.add(d)
    await session.flush()
    v = _store(session, d.id, 1, name, content_type, data, actor)
    await session.flush()
    session.add(DocumentBlob(version_id=v.id, data=data))
    await _audit(
        session, actor, "document.upload", d.id, meta, {"filename": name, "size": len(data)}
    )
    await session.commit()
    return d


async def add_version(session, actor, principal, document_id, filename, data, note, meta):
    d = await get_document(session, principal, document_id, "document.update")
    name, content_type = validate_file(filename, data)
    d.current_version += 1
    v = _store(session, d.id, d.current_version, name, content_type, data, actor, note)
    await session.flush()
    session.add(DocumentBlob(version_id=v.id, data=data))
    await _audit(session, actor, "document.version", d.id, meta, {"version": d.current_version})
    await session.commit()
    await session.refresh(d)
    return d


async def update(session, actor, principal, document_id, payload: DocumentPatch, meta):
    d = await get_document(session, principal, document_id, "document.update")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if value is None:
            if field == "description":
                value = ""
            else:
                raise AppError(f"{field.title()} cannot be empty.", code="invalid_field")
        setattr(d, field, value)
    await _audit(session, actor, "document.update", d.id, meta, {"fields": sorted(changes)})
    await session.commit()
    await session.refresh(d)
    return d


async def set_members(session, actor, principal, document_id, payload: MembersIn, meta):
    d = await get_document(session, principal, document_id, "document.update")
    ids = set(payload.user_ids)
    if ids:
        found = set(
            await session.scalars(
                select(User.id).where(
                    User.id.in_(ids),
                    User.company_id == actor.company_id,
                    User.status == UserStatus.ACTIVE,
                )
            )
        )
        if found != ids:
            raise AppError("Every member must be an active user.", code="invalid_user")
    existing = {
        m.user_id: m
        for m in await session.scalars(
            select(DocumentMember).where(DocumentMember.document_id == d.id)
        )
    }
    for uid, member in existing.items():
        if uid not in ids:
            await session.delete(member)
    for uid in ids - existing.keys():
        session.add(DocumentMember(document_id=d.id, user_id=uid))
    await _audit(session, actor, "document.members", d.id, meta, {"members": len(ids)})
    await session.commit()
    return d


async def delete(session, actor, principal, document_id, meta) -> None:
    d = await get_document(session, principal, document_id, "document.delete")
    await _audit(session, actor, "document.delete", d.id, meta, {"title": d.title})
    await session.delete(d)
    await session.commit()


async def download(session, actor, principal, document_id, version: int | None, meta):
    d = await get_document(session, principal, document_id)
    v = await session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == d.id,
            DocumentVersion.version == (version or d.current_version),
        )
    )
    if v is None:
        raise NotFoundError("Version not found.")
    data = await session.scalar(select(DocumentBlob.data).where(DocumentBlob.version_id == v.id))
    await _audit(session, actor, "document.download", d.id, meta, {"version": v.version})
    await session.commit()
    return v, data
