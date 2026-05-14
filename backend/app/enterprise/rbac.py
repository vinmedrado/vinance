from __future__ import annotations

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "owner": {"*"},
    "admin": {
        "expenses.view", "expenses.create", "expenses.edit", "expenses.delete",
        "incomes.view", "incomes.create", "incomes.edit", "incomes.delete",
        "budgets.view", "budgets.manage",
        "goals.view", "goals.create", "goals.edit", "goals.delete",
        "accounts.view", "accounts.manage", "cards.view", "cards.manage",
        "investments.view", "investments.manage", "portfolio.view", "portfolio.manage",
        "alerts.view", "alerts.manage", "diagnosis.view",
        "jobs.view", "jobs.run", "admin.access",
        "billing.view", "billing.manage",
        "users.view", "users.invite", "users.manage_roles", "users.remove",
        "analytics.view", "audit.view", "health.admin",
    },
    "finance_manager": {
        "expenses.view", "expenses.create", "expenses.edit",
        "incomes.view", "incomes.create", "incomes.edit",
        "budgets.view", "budgets.manage",
        "goals.view", "goals.create", "goals.edit",
        "accounts.view", "accounts.manage", "cards.view", "cards.manage",
        "investments.view", "portfolio.view", "alerts.view", "alerts.manage",
        "diagnosis.view", "analytics.view", "audit.view",
    },
    "analyst": {
        "expenses.view", "incomes.view", "budgets.view", "goals.view",
        "accounts.view", "cards.view", "investments.view", "portfolio.view",
        "alerts.view", "diagnosis.view", "jobs.view", "analytics.view",
    },
    "member": {
        "expenses.view", "expenses.create", "expenses.edit",
        "incomes.view", "incomes.create", "incomes.edit",
        "budgets.view", "goals.view", "goals.create", "goals.edit",
        "accounts.view", "cards.view", "investments.view", "portfolio.view",
        "alerts.view", "diagnosis.view",
    },
    "viewer": {
        "expenses.view", "incomes.view", "budgets.view", "goals.view",
        "accounts.view", "cards.view", "investments.view", "portfolio.view",
        "alerts.view", "diagnosis.view",
    },
}

DEFAULT_ROLES = tuple(ROLE_PERMISSIONS.keys())
DEFAULT_PERMISSIONS = sorted({p for values in ROLE_PERMISSIONS.values() for p in values if p != "*"})
LEGACY_PERMISSION_ALIASES = {
    "finance.view": "expenses.view",
    "budget.manage": "budgets.manage",
    "users.manage": "users.manage_roles",
    "backtests.run": "jobs.run",
}

def has_permission(role: str | None, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get((role or "viewer").lower(), set())
    permission = LEGACY_PERMISSION_ALIASES.get(permission, permission)
    return "*" in permissions or permission in permissions
