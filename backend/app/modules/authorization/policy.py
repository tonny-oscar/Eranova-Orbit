"""Pure authorization policy. No I/O, so every rule is unit-testable.

A user's effective access is a set of grants: (permission key, scope). A grant
applies to a target resource when its scope covers that resource:

* company    - any resource in the user's company
* department - resources belonging to that department
* product    - resources linked to that product
* project    - resources belonging to that project
* own        - resources the user owns
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from app.modules.authorization.catalogue import ScopeType


@dataclass(frozen=True)
class Grant:
    scope_type: ScopeType
    scope_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ResourceContext:
    """What the policy needs to know about the record being accessed."""

    company_id: uuid.UUID
    department_id: uuid.UUID | None = None
    product_ids: frozenset[uuid.UUID] = frozenset()
    project_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None


@dataclass
class Principal:
    user_id: uuid.UUID
    company_id: uuid.UUID
    grants: dict[str, set[Grant]] = field(default_factory=lambda: defaultdict(set))

    @property
    def permission_keys(self) -> set[str]:
        return {key for key, grants in self.grants.items() if grants}

    def grants_for(self, permission: str) -> set[Grant]:
        return self.grants.get(permission, set())


def grant_covers_resource(grant: Grant, principal: Principal, target: ResourceContext) -> bool:
    if target.company_id != principal.company_id:
        return False
    match grant.scope_type:
        case ScopeType.COMPANY:
            return True
        case ScopeType.DEPARTMENT:
            return grant.scope_id is not None and grant.scope_id == target.department_id
        case ScopeType.PRODUCT:
            return grant.scope_id is not None and grant.scope_id in target.product_ids
        case ScopeType.PROJECT:
            return grant.scope_id is not None and grant.scope_id == target.project_id
        case ScopeType.OWN:
            return target.owner_user_id == principal.user_id
    return False


def is_allowed(
    principal: Principal, permission: str, target: ResourceContext | None = None
) -> bool:
    """Check a permission.

    With ``target=None`` this answers "may the user perform this action on at
    least some records?" (e.g. may they open the list view). Queries must then
    be filtered to the user's scopes; this check alone does not authorize
    access to any individual record.
    """
    grants = principal.grants_for(permission)
    if not grants:
        return False
    if target is None:
        return True
    return any(grant_covers_resource(g, principal, target) for g in grants)


@dataclass(frozen=True)
class ScopeFilter:
    """The set of records a principal may access for one permission.

    Services translate this into WHERE clauses for list queries.
    """

    company_wide: bool = False
    department_ids: frozenset[uuid.UUID] = frozenset()
    product_ids: frozenset[uuid.UUID] = frozenset()
    project_ids: frozenset[uuid.UUID] = frozenset()
    own: bool = False

    @property
    def is_empty(self) -> bool:
        return not (
            self.company_wide
            or self.department_ids
            or self.product_ids
            or self.project_ids
            or self.own
        )


def scope_filter(principal: Principal, permission: str) -> ScopeFilter:
    grants = principal.grants_for(permission)
    ids: dict[ScopeType, set[uuid.UUID]] = defaultdict(set)
    company_wide = own = False
    for grant in grants:
        if grant.scope_type == ScopeType.COMPANY:
            company_wide = True
        elif grant.scope_type == ScopeType.OWN:
            own = True
        elif grant.scope_id is not None:
            ids[grant.scope_type].add(grant.scope_id)
    return ScopeFilter(
        company_wide=company_wide,
        department_ids=frozenset(ids[ScopeType.DEPARTMENT]),
        product_ids=frozenset(ids[ScopeType.PRODUCT]),
        project_ids=frozenset(ids[ScopeType.PROJECT]),
        own=own,
    )


def grant_covers_grant(held: Grant, requested: Grant) -> bool:
    """Whether holding ``held`` is enough authority to hand out ``requested``."""
    if held.scope_type == ScopeType.COMPANY:
        return True
    return held.scope_type == requested.scope_type and held.scope_id == requested.scope_id


def can_delegate(principal: Principal, permissions: set[str], scope: Grant) -> set[str]:
    """Return the subset of ``permissions`` the principal could NOT delegate at ``scope``.

    Prevents privilege escalation: an administrator can only assign roles whose
    every permission they already hold at an equal or broader scope.
    """
    return {
        key
        for key in permissions
        if not any(grant_covers_grant(held, scope) for held in principal.grants_for(key))
    }
