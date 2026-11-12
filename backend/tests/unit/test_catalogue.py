from app.modules.authorization.catalogue import (
    PERMISSION_CATALOGUE,
    PERMISSION_KEYS,
    STARTER_ROLES,
    SUPER_ADMIN_SLUG,
)


def test_permission_keys_are_unique():
    assert len(PERMISSION_KEYS) == len(PERMISSION_CATALOGUE)


def test_starter_roles_only_reference_catalogue_permissions():
    for role in STARTER_ROLES:
        unknown = set(role.permissions) - PERMISSION_KEYS
        assert not unknown, f"{role.slug} references unknown permissions {unknown}"


def test_starter_role_slugs_are_unique():
    slugs = [r.slug for r in STARTER_ROLES]
    assert len(slugs) == len(set(slugs))


def test_only_super_admin_is_locked_and_holds_everything():
    locked = [r for r in STARTER_ROLES if r.locked]
    assert [r.slug for r in locked] == [SUPER_ADMIN_SLUG]
    assert set(locked[0].permissions) == PERMISSION_KEYS


def test_auditor_is_read_only():
    auditor = next(r for r in STARTER_ROLES if r.slug == "auditor")
    assert all(key.endswith(".read") for key in auditor.permissions)
    assert "audit_log.read" in auditor.permissions


def test_privileged_platform_permissions_are_sensitive():
    sensitive = {p.key for p in PERMISSION_CATALOGUE if p.is_sensitive}
    for key in (
        "role.manage",
        "role.update",
        "user.manage",
        "settings.update",
        "invoice.approve",
        "audit_log.read",
    ):
        assert key in sensitive


def test_non_admin_starter_roles_cannot_manage_roles():
    for role in STARTER_ROLES:
        if role.slug != SUPER_ADMIN_SLUG:
            assert "role.manage" not in role.permissions, role.slug
