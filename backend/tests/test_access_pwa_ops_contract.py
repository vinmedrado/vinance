from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_secret_preparation_generates_server_secrets_without_printing_them() -> None:
    script_path = ROOT / "deploy" / "prepare-access-pwa-secrets.ps1"
    assert script_path.exists()
    source = script_path.read_text(encoding="utf-8")

    for contract in (
        "RandomNumberGenerator",
        "ExportECPrivateKey",
        "CreateFromFriendlyName",
        "BOOTSTRAP_TOKEN_HASH",
        "PUSH_SUBSCRIPTION_ENCRYPTION_KEY",
        "VAPID_PUBLIC_KEY",
        "VAPID_PRIVATE_KEY",
        "MIGRATION_DATABASE_URL",
        "RUNTIME_DATABASE_URL",
        "icacls",
        "chmod",
    ):
        assert contract in source
    assert "Write-Host $bootstrap" not in source
    assert "Write-Output $bootstrap" not in source
    assert "::NamedCurves" not in source
    assert ".private/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_runtime_role_preparation_enforces_least_privilege_and_default_grants() -> None:
    source = (ROOT / "deploy" / "postgres" / "prepare-runtime-role.ps1").read_text(encoding="utf-8")

    for contract in (
        "NOSUPERUSER",
        "NOCREATEDB",
        "NOCREATEROLE",
        "NOBYPASSRLS",
        "ALTER DEFAULT PRIVILEGES",
        "GRANT SELECT, INSERT, UPDATE, DELETE",
    ):
        assert contract in source
    assert "@(& docker compose" in source
    assert "-join" in source


def test_backup_profile_uses_the_documented_backup_database_url() -> None:
    compose = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
    backup_block = compose.split("\n  backup:\n", 1)[1].split("\nnetworks:\n", 1)[0]

    assert "BACKUP_DATABASE_URL: ${BACKUP_DATABASE_URL:?BACKUP_DATABASE_URL is required}" in backup_block
    assert "DATABASE_URL: ${BACKUP_DATABASE_URL:?BACKUP_DATABASE_URL is required}" in backup_block
    assert "DATABASE_URL: ${DATABASE_URL:?DATABASE_URL is required}" not in backup_block
