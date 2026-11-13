"""Import every model so ``Base.metadata`` is complete for Alembic autogenerate."""

from app.db.base import Base
from app.modules.audit.models import AuditLog
from app.modules.authorization.models import Permission, Role, RolePermission, UserRole
from app.modules.company.models import Company
from app.modules.content.models import ContentPage
from app.modules.crm.models import (
    Activity,
    Contact,
    Customer,
    CustomerProduct,
    Enquiry,
    Lead,
    PipelineStage,
)
from app.modules.identity.models import LoginAttempt, User, UserSession
from app.modules.people.models import Department, EmployeeProfile
from app.modules.products.models import Product, ProductMember, ProductStatusHistory

__all__ = [
    "Activity",
    "AuditLog",
    "Base",
    "Company",
    "Contact",
    "ContentPage",
    "Customer",
    "CustomerProduct",
    "Department",
    "EmployeeProfile",
    "Enquiry",
    "Lead",
    "LoginAttempt",
    "Permission",
    "PipelineStage",
    "Product",
    "ProductMember",
    "ProductStatusHistory",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
    "UserSession",
]
