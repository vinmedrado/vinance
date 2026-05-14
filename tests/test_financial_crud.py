def test_financial_crud_routes_are_tenant_safe_by_contract():
    from pathlib import Path
    router = Path("backend/app/erp/router.py").read_text()
    assert "ERPExpense.organization_id == _tenant(ctx)" in router
    assert "require_permission(\"expenses.create\")" in router
    assert "expense.created" in router
    assert "Plan limit reached" in router
