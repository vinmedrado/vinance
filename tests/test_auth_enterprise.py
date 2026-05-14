from backend.app.enterprise.security import sha256_token


def test_token_hash_is_deterministic_and_not_plain():
    token = "abc"
    assert sha256_token(token) == sha256_token(token)
    assert sha256_token(token) != token


def test_auth_uses_organizations_not_legacy_tenants():
    from pathlib import Path
    router = Path("backend/app/auth/router.py").read_text()
    assert "organization_members" in router
    assert "organizations" in router
    assert "INSERT INTO tenants" not in router
    assert "INSERT INTO tenants" not in router
