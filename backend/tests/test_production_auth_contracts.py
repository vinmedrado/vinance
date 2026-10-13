from pathlib import Path

from backend.app.auth.models import AuthSession
from backend.app.auth.security import (
    create_access_token,
    decode_access_token_claims,
    generate_refresh_token,
    hash_refresh_token,
)


ROOT = Path(__file__).resolve().parents[2]


def test_access_token_carries_revocable_session_and_unique_token_id() -> None:
    token = create_access_token("user@example.com", session_id="session-123")
    claims = decode_access_token_claims(token)
    assert claims is not None
    assert claims.subject == "user@example.com"
    assert claims.session_id == "session-123"
    assert claims.token_id


def test_refresh_credential_is_opaque_and_only_digest_fits_persistence_contract() -> None:
    refresh = generate_refresh_token()
    digest = hash_refresh_token(refresh)
    assert len(refresh) >= 48
    assert len(digest) == 64
    assert refresh not in digest
    assert hash_refresh_token(refresh) == digest


def test_auth_session_schema_has_revocation_and_expiry_fields() -> None:
    columns = AuthSession.__table__.columns
    assert {"id", "user_id", "refresh_token_hash", "expires_at", "last_used_at", "revoked_at"} <= set(columns.keys())
    assert columns.refresh_token_hash.type.length == 64


def test_frontend_does_not_persist_bearer_token_in_web_storage() -> None:
    api_source = (ROOT / "frontend" / "src" / "services" / "api.ts").read_text(encoding="utf-8")
    assert "localStorage.setItem" not in api_source
    assert "sessionStorage.setItem" not in api_source
    assert "withCredentials: true" in api_source


def test_admin_recovery_reads_password_interactively() -> None:
    source = (ROOT / "backend" / "app" / "operations" / "admin_account.py").read_text(encoding="utf-8")
    assert "getpass(" in source
    assert 'choices=("reset-password", "revoke-sessions")' in source
    assert "revoke_all_user_sessions" in source
