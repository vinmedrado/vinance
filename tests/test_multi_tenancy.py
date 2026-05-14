def test_context_contract_mentions_organization_context():
    from pathlib import Path
    context = Path("backend/app/enterprise/context.py").read_text()
    assert "class OrganizationContext" in context
    assert "organization_id" in context
    assert "get_organization_context" in context


def test_business_query_must_include_organization_filter():
    router = __import__("pathlib").Path("backend/app/erp/router.py").read_text()
    assert "organization_id == _tenant(ctx)" in router
    assert "organization_id=_tenant(ctx)" in router
