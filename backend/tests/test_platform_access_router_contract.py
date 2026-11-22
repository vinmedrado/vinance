from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_every_admin_mutation_is_rate_limited() -> None:
    source = (ROOT / "backend" / "app" / "platform_access" / "router.py").read_text(
        encoding="utf-8"
    )

    expected_scopes = (
        "platform-invitation-create",
        "platform-invitation-resend",
        "platform-invitation-cancel",
        "platform-user-deactivate",
        "platform-user-activate",
        "platform-password-reset-link",
    )
    for scope in expected_scopes:
        assert f'"{scope}"' in source


def test_logout_revokes_the_current_push_installation_server_side() -> None:
    router = (ROOT / "backend" / "app" / "auth" / "router.py").read_text(encoding="utf-8")
    sessions = (ROOT / "backend" / "app" / "auth" / "sessions.py").read_text(
        encoding="utf-8"
    )
    frontend = (
        ROOT
        / "frontend"
        / "src"
        / "features"
        / "auth"
        / "services"
        / "auth.service.ts"
    ).read_text(encoding="utf-8")

    assert 'request.headers.get("x-vinance-installation-id")' in router
    assert "revoke_installation" in router
    assert "user_id = record.user_id" in sessions
    assert "return user_id" in sessions
    assert "X-Vinance-Installation-ID" in frontend
