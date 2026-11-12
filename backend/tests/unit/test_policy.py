import uuid

from app.modules.authorization.catalogue import ScopeType
from app.modules.authorization.policy import (
    Grant,
    Principal,
    ResourceContext,
    can_delegate,
    is_allowed,
)

COMPANY = uuid.uuid4()
OTHER_COMPANY = uuid.uuid4()
USER = uuid.uuid4()
PRODUCT_A = uuid.uuid4()
PRODUCT_B = uuid.uuid4()
PROJECT = uuid.uuid4()
DEPARTMENT = uuid.uuid4()


def principal(**grants: set[Grant]) -> Principal:
    p = Principal(user_id=USER, company_id=COMPANY)
    for key, value in grants.items():
        p.grants[key.replace("__", ".")] = value
    return p


def test_no_grant_denies():
    assert not is_allowed(principal(), "product.read")


def test_collection_check_passes_with_any_grant():
    p = principal(product__read={Grant(ScopeType.PRODUCT, PRODUCT_A)})
    assert is_allowed(p, "product.read")


def test_company_scope_covers_any_record_in_company():
    p = principal(task__read={Grant(ScopeType.COMPANY)})
    assert is_allowed(p, "task.read", ResourceContext(company_id=COMPANY))


def test_company_scope_never_crosses_company_boundary():
    p = principal(task__read={Grant(ScopeType.COMPANY)})
    assert not is_allowed(p, "task.read", ResourceContext(company_id=OTHER_COMPANY))


def test_product_scope_only_matches_linked_products():
    p = principal(lead__update={Grant(ScopeType.PRODUCT, PRODUCT_A)})
    assert is_allowed(
        p, "lead.update", ResourceContext(COMPANY, product_ids=frozenset({PRODUCT_A}))
    )
    assert not is_allowed(
        p, "lead.update", ResourceContext(COMPANY, product_ids=frozenset({PRODUCT_B}))
    )


def test_project_and_department_scopes():
    p = principal(
        task__update={Grant(ScopeType.PROJECT, PROJECT)},
        employee__read={Grant(ScopeType.DEPARTMENT, DEPARTMENT)},
    )
    assert is_allowed(p, "task.update", ResourceContext(COMPANY, project_id=PROJECT))
    assert not is_allowed(p, "task.update", ResourceContext(COMPANY, project_id=uuid.uuid4()))
    assert is_allowed(p, "employee.read", ResourceContext(COMPANY, department_id=DEPARTMENT))
    assert not is_allowed(p, "employee.read", ResourceContext(COMPANY))


def test_own_scope_requires_ownership():
    p = principal(task__update={Grant(ScopeType.OWN)})
    assert is_allowed(p, "task.update", ResourceContext(COMPANY, owner_user_id=USER))
    assert not is_allowed(p, "task.update", ResourceContext(COMPANY, owner_user_id=uuid.uuid4()))


def test_permission_for_one_action_does_not_imply_another():
    p = principal(task__read={Grant(ScopeType.COMPANY)})
    assert not is_allowed(p, "task.delete", ResourceContext(COMPANY))


def test_delegation_requires_equal_or_broader_scope():
    p = principal(
        task__read={Grant(ScopeType.COMPANY)},
        task__update={Grant(ScopeType.PROJECT, PROJECT)},
    )
    assert can_delegate(p, {"task.read"}, Grant(ScopeType.PROJECT, PROJECT)) == set()
    assert can_delegate(p, {"task.update"}, Grant(ScopeType.PROJECT, PROJECT)) == set()
    assert can_delegate(p, {"task.update"}, Grant(ScopeType.COMPANY)) == {"task.update"}
    assert can_delegate(p, {"task.update"}, Grant(ScopeType.PROJECT, uuid.uuid4())) == {
        "task.update"
    }


def test_delegation_reports_permissions_actor_lacks():
    p = principal(role__manage={Grant(ScopeType.COMPANY)})
    assert can_delegate(p, {"role.manage", "invoice.approve"}, Grant(ScopeType.COMPANY)) == {
        "invoice.approve"
    }
