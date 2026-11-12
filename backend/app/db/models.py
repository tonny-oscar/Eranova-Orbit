"""Import every model so ``Base.metadata`` is complete for Alembic autogenerate."""

from app.db.base import Base
from app.modules.audit.models import AuditLog
from app.modules.authorization.models import Permission, Role, RolePermission, UserRole
from app.modules.company.models import Company
from app.modules.identity.models import LoginAttempt, User, UserSession
from app.modules.products.models import Product, ProductMember, ProductStatusHistory

__all__ = [
    "AuditLog",
    "Base",
    "Company",
    "LoginAttempt",
    "Permission",
    "Product",
    "ProductMember",
    "ProductStatusHistory",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
    "UserSession",
]
