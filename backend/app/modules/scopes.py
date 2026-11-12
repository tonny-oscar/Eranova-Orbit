"""Wires scope types to the modules that own their target records."""

from app.modules.authorization.catalogue import ScopeType
from app.modules.authorization.service import SCOPE_VALIDATORS
from app.modules.people.service import department_exists
from app.modules.products.service import product_exists


def register_scope_validators() -> None:
    SCOPE_VALIDATORS[ScopeType.PRODUCT] = product_exists
    SCOPE_VALIDATORS[ScopeType.DEPARTMENT] = department_exists
