from backend.app.enterprise.rbac import ROLE_PERMISSIONS, has_permission


def test_owner_admin_permissions():
    assert has_permission("owner", "billing.manage") is True
    assert has_permission("admin", "expenses.create") is True
    assert has_permission("admin", "users.manage_roles") is True


def test_viewer_and_member_restrictions():
    assert has_permission("viewer", "expenses.create") is False
    assert has_permission("viewer", "expenses.view") is True
    assert has_permission("member", "billing.manage") is False
    assert has_permission("member", "admin.access") is False


def test_required_permission_matrix_exists():
    required = {"expenses.view", "expenses.create", "expenses.edit", "expenses.delete", "billing.manage", "users.manage_roles", "audit.view"}
    flattened = set().union(*[v for v in ROLE_PERMISSIONS.values() if "*" not in v])
    assert required.issubset(flattened)
