"""Executive summary and global search.

Every figure is computed live from the Orbit database and respects the
caller's permission scopes. Sections the caller cannot access are omitted,
never zero-filled, so the UI cannot mistake "no access" for "no data".
"""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.authorization.policy import Principal, ResourceContext, is_allowed, scope_filter
from app.modules.identity.models import User, UserStatus
from app.modules.identity.service import utcnow
from app.modules.people.models import Department
from app.modules.people.service import department_member_condition, escape_like
from app.modules.products.models import Product
from app.modules.products.service import product_scope_condition


@dataclass
class Summary:
    generated_at: datetime
    products: dict | None = None
    people: dict | None = None
    accounts: dict | None = None
    recent_activity: list[AuditLog] | None = None


def _company_wide(principal: Principal, permission: str) -> bool:
    return is_allowed(principal, permission, ResourceContext(company_id=principal.company_id))


async def build_summary(session: AsyncSession, principal: Principal) -> Summary:
    summary = Summary(generated_at=utcnow())

    if is_allowed(principal, "product.read"):
        visible = [
            Product.company_id == principal.company_id,
            product_scope_condition(scope_filter(principal, "product.read"), principal.user_id),
        ]
        by_status = dict(
            (
                await session.execute(
                    select(Product.lifecycle_status, func.count())
                    .where(*visible)
                    .group_by(Product.lifecycle_status)
                )
            ).all()
        )
        unconfirmed = await session.scalar(
            select(func.count())
            .select_from(Product)
            .where(*visible, Product.details_confirmed.is_(False))
        )
        summary.products = {
            "total": sum(by_status.values()),
            "by_status": by_status,
            "unconfirmed": unconfirmed or 0,
        }

    if is_allowed(principal, "employee.read"):
        people = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.company_id == principal.company_id,
                User.status == UserStatus.ACTIVE,
                department_member_condition(principal, "employee.read"),
            )
        )
        departments = await session.scalar(
            select(func.count())
            .select_from(Department)
            .where(Department.company_id == principal.company_id)
        )
        summary.people = {"active": people or 0, "departments": departments or 0}

    if _company_wide(principal, "user.read"):
        rows = dict(
            (
                await session.execute(
                    select(User.status, func.count())
                    .where(User.company_id == principal.company_id)
                    .group_by(User.status)
                )
            ).all()
        )
        awaiting = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.company_id == principal.company_id,
                User.status == UserStatus.ACTIVE,
                User.must_change_password.is_(True),
            )
        )
        summary.accounts = {
            "active": rows.get(UserStatus.ACTIVE, 0),
            "disabled": rows.get(UserStatus.DISABLED, 0),
            "awaiting_first_sign_in": awaiting or 0,
        }

    if _company_wide(principal, "audit_log.read"):
        summary.recent_activity = list(
            await session.scalars(
                select(AuditLog)
                .where(AuditLog.company_id == principal.company_id)
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(8)
            )
        )
    return summary


@dataclass
class SearchResult:
    type: str
    id: str
    title: str
    subtitle: str | None
    url: str


@dataclass
class SearchResults:
    query: str
    results: list[SearchResult] = field(default_factory=list)


async def search(
    session: AsyncSession, principal: Principal, q: str, limit: int = 5
) -> SearchResults:
    term = q.strip()
    found = SearchResults(query=term)
    if len(term) < 2:
        return found
    pattern = f"%{escape_like(term.lower())}%"

    if is_allowed(principal, "product.read"):
        products = await session.scalars(
            select(Product)
            .where(
                Product.company_id == principal.company_id,
                product_scope_condition(scope_filter(principal, "product.read"), principal.user_id),
                or_(
                    func.lower(Product.name).like(pattern, escape="\\"),
                    Product.slug.like(pattern, escape="\\"),
                    func.lower(func.coalesce(Product.category, "")).like(pattern, escape="\\"),
                ),
            )
            .order_by(Product.name)
            .limit(limit)
        )
        found.results += [
            SearchResult(
                type="product",
                id=str(p.id),
                title=p.name,
                subtitle=p.category or p.slug,
                url=f"/app/products/{p.id}",
            )
            for p in products
        ]

    people_permission = (
        "employee.read"
        if is_allowed(principal, "employee.read")
        else "user.read"
        if is_allowed(principal, "user.read")
        else None
    )
    if people_permission:
        users = await session.scalars(
            select(User)
            .where(
                User.company_id == principal.company_id,
                User.status != UserStatus.DISABLED,
                department_member_condition(principal, people_permission),
                or_(
                    func.lower(User.full_name).like(pattern, escape="\\"),
                    User.email.like(pattern, escape="\\"),
                ),
            )
            .order_by(User.full_name)
            .limit(limit)
        )
        base = "/app/team" if people_permission == "employee.read" else "/app/settings/users"
        found.results += [
            SearchResult(
                type="person",
                id=str(u.id),
                title=u.full_name,
                subtitle=u.email,
                url=f"{base}/{u.id}",
            )
            for u in users
        ]
    return found
