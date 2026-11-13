"""Code-owned permission catalogue and starter roles.

The catalogue is synchronised into the database by ``app.cli bootstrap``.
Starter roles are created once; afterwards administrators may customise them,
and bootstrap will not overwrite those changes (except the locked Super Admin
role, which always holds every permission).
"""

from dataclasses import dataclass
from enum import StrEnum


class Action(StrEnum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    EXPORT = "export"
    MANAGE = "manage"


class ScopeType(StrEnum):
    COMPANY = "company"
    DEPARTMENT = "department"
    PRODUCT = "product"
    PROJECT = "project"
    OWN = "own"


CRUD = (Action.READ, Action.CREATE, Action.UPDATE, Action.DELETE)
ALL_ACTIONS = tuple(Action)

# resource -> (human label, supported actions)
RESOURCES: dict[str, tuple[str, tuple[Action, ...]]] = {
    # Business resources (architecture §6)
    "product": ("products", ALL_ACTIONS),
    "lead": ("CRM leads", ALL_ACTIONS),
    "customer": ("customers", ALL_ACTIONS),
    "project": ("projects", ALL_ACTIONS),
    "task": ("tasks", ALL_ACTIONS),
    "employee": ("employee records", ALL_ACTIONS),
    "campaign": ("marketing campaigns", ALL_ACTIONS),
    "invoice": ("invoices", ALL_ACTIONS),
    "ticket": ("support tickets", ALL_ACTIONS),
    "document": ("documents", ALL_ACTIONS),
    "integration": ("integrations", ALL_ACTIONS),
    "report": ("reports", (Action.READ, Action.CREATE, Action.EXPORT, Action.MANAGE)),
    # Public website content; "approve" publishes to the public site.
    "content": ("website content", (Action.READ, Action.UPDATE, Action.APPROVE)),
    # Platform administration
    "user": ("user accounts", (*CRUD, Action.MANAGE)),
    "role": ("roles and role assignments", (*CRUD, Action.MANAGE)),
    "audit_log": ("audit logs", (Action.READ, Action.EXPORT)),
    "settings": ("company settings", (Action.READ, Action.UPDATE)),
}

_SENSITIVE_ACTIONS = {Action.DELETE, Action.APPROVE, Action.EXPORT, Action.MANAGE}
_SENSITIVE_RESOURCES = {"role", "user", "settings", "integration", "audit_log", "invoice"}
# Read access that is itself privileged; denied attempts are audited.
_SENSITIVE_READS = {"audit_log.read", "invoice.read"}

_ACTION_VERBS = {
    Action.READ: "View",
    Action.CREATE: "Create",
    Action.UPDATE: "Edit",
    Action.DELETE: "Delete",
    Action.APPROVE: "Approve",
    Action.EXPORT: "Export",
    Action.MANAGE: "Fully administer",
}


@dataclass(frozen=True)
class PermissionDef:
    key: str
    resource: str
    action: Action
    description: str
    is_sensitive: bool


def permission_key(resource: str, action: Action | str) -> str:
    return f"{resource}.{action}"


def build_permission_catalogue() -> list[PermissionDef]:
    catalogue: list[PermissionDef] = []
    for resource, (label, actions) in RESOURCES.items():
        for action in actions:
            catalogue.append(
                PermissionDef(
                    key=permission_key(resource, action),
                    resource=resource,
                    action=action,
                    description=f"{_ACTION_VERBS[action]} {label}",
                    is_sensitive=action in _SENSITIVE_ACTIONS
                    or (resource in _SENSITIVE_RESOURCES and action != Action.READ)
                    or permission_key(resource, action) in _SENSITIVE_READS,
                )
            )
    return catalogue


PERMISSION_CATALOGUE = build_permission_catalogue()
PERMISSION_KEYS = frozenset(p.key for p in PERMISSION_CATALOGUE)


def _keys(resource: str, *actions: Action) -> list[str]:
    return [permission_key(resource, a) for a in actions]


def _read_all(resources: list[str]) -> list[str]:
    return [permission_key(r, Action.READ) for r in resources]


_BUSINESS = [r for r in RESOURCES if r not in ("user", "role", "audit_log", "settings")]

SUPER_ADMIN_SLUG = "super_admin"


@dataclass(frozen=True)
class StarterRole:
    slug: str
    name: str
    description: str
    permissions: tuple[str, ...]
    locked: bool = False


STARTER_ROLES: tuple[StarterRole, ...] = (
    StarterRole(
        SUPER_ADMIN_SLUG,
        "Super Admin",
        "Company owner. Holds every permission; cannot be edited.",
        tuple(sorted(PERMISSION_KEYS)),
        locked=True,
    ),
    StarterRole(
        "executive",
        "Executive",
        "Company-wide visibility, reporting and approvals.",
        tuple(
            _read_all(_BUSINESS)
            + _keys("report", Action.CREATE, Action.EXPORT)
            + _keys("project", Action.APPROVE)
            + _keys("invoice", Action.APPROVE)
            + _keys("product", Action.APPROVE)
            + _keys("content", Action.APPROVE)
            + _read_all(["user", "role", "settings"])
        ),
    ),
    StarterRole(
        "department_manager",
        "Department Manager",
        "Manages people and work within an assigned department.",
        tuple(
            _keys("employee", Action.READ, Action.UPDATE)
            + _keys("project", Action.READ, Action.CREATE, Action.UPDATE)
            + _keys("task", Action.READ, Action.CREATE, Action.UPDATE, Action.APPROVE)
            + _keys("report", Action.READ, Action.CREATE)
            + _keys("document", Action.READ, Action.CREATE)
            + _read_all(["product", "user"])
        ),
    ),
    StarterRole(
        "product_manager",
        "Product Manager",
        "Owns an assigned product's roadmap, work and go-to-market.",
        tuple(
            _keys("product", Action.READ, Action.UPDATE)
            + _keys("project", Action.READ, Action.CREATE, Action.UPDATE)
            + _keys("task", Action.READ, Action.CREATE, Action.UPDATE, Action.APPROVE)
            + _keys("campaign", Action.READ, Action.CREATE, Action.UPDATE)
            + _keys("report", Action.READ, Action.CREATE)
            + _keys("document", Action.READ, Action.CREATE, Action.UPDATE)
            + _read_all(["lead", "customer", "ticket", "integration"])
        ),
    ),
    StarterRole(
        "project_manager",
        "Project Manager",
        "Plans and reviews work for assigned projects.",
        tuple(
            _keys("project", Action.READ, Action.UPDATE)
            + _keys("task", *CRUD, Action.APPROVE)
            + _keys("document", Action.READ, Action.CREATE)
            + _keys("report", Action.READ)
            + _read_all(["product"])
        ),
    ),
    StarterRole(
        "developer",
        "Developer",
        "Works on assigned products and tasks.",
        tuple(
            _keys("task", Action.READ, Action.UPDATE)
            + _read_all(["product", "project", "document", "integration"])
        ),
    ),
    StarterRole(
        "sales",
        "Sales",
        "Works leads and customer relationships.",
        tuple(
            _keys("lead", Action.READ, Action.CREATE, Action.UPDATE)
            + _keys("customer", Action.READ, Action.CREATE, Action.UPDATE)
            + _keys("task", Action.READ, Action.CREATE, Action.UPDATE)
            + _read_all(["product", "report", "document"])
        ),
    ),
    StarterRole(
        "marketing",
        "Marketing",
        "Plans campaigns and content.",
        tuple(
            _keys("campaign", Action.READ, Action.CREATE, Action.UPDATE)
            + _keys("document", Action.READ, Action.CREATE)
            + _keys("content", Action.READ, Action.UPDATE)
            + _read_all(["product", "lead", "report"])
        ),
    ),
    StarterRole(
        "hr",
        "HR",
        "Manages employee records.",
        tuple(
            _keys("employee", Action.READ, Action.CREATE, Action.UPDATE)
            + _keys("document", Action.READ, Action.CREATE)
            + _read_all(["user"])
        ),
    ),
    StarterRole(
        "finance",
        "Finance",
        "Manages invoices and financial reporting.",
        tuple(
            _keys("invoice", Action.READ, Action.CREATE, Action.UPDATE, Action.EXPORT)
            + _keys("report", Action.READ, Action.CREATE, Action.EXPORT)
            + _read_all(["customer", "product"])
        ),
    ),
    StarterRole(
        "support",
        "Support",
        "Handles customer support tickets.",
        tuple(
            _keys("ticket", Action.READ, Action.CREATE, Action.UPDATE)
            + _read_all(["customer", "product", "document"])
        ),
    ),
    StarterRole(
        "employee",
        "Employee / Intern",
        "Baseline access; typically assigned with the 'own' scope.",
        tuple(_keys("task", Action.READ, Action.UPDATE) + _read_all(["product", "document"])),
    ),
    StarterRole(
        "auditor",
        "Read-only Auditor",
        "Read-only access including audit logs.",
        tuple(_read_all(list(RESOURCES))),
    ),
)
