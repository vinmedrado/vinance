from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_backup_is_encrypted_checksummed_and_fails_closed() -> None:
    source = (ROOT / "deploy" / "backup" / "backup.sh").read_text(encoding="utf-8")
    assert "set -Eeuo pipefail" in source
    assert "pg_dump --format=custom" in source
    assert "aes-256-cbc" in source and "-pbkdf2" in source
    assert "sha256sum" in source
    assert "pg_dump --format=custom" in source and "| openssl enc" in source
    assert "test -s \"$encrypted_tmp\"" in source
    assert "$(basename \"$encrypted\")" in source
    assert "BACKUP_DAILY_KEEP:-7" in source
    assert "BACKUP_WEEKLY_KEEP:-4" in source
    assert "BACKUP_MONTHLY_KEEP:-3" in source


def test_restore_refuses_canonical_or_non_empty_target() -> None:
    source = (ROOT / "deploy" / "backup" / "restore.sh").read_text(encoding="utf-8")
    assert "Refusing to restore into DATABASE_URL" in source
    assert "Refusing to restore into canonical database" in source
    assert "Target database must be empty" in source
    assert "RESTORE_DATABASE_URL" in source
    assert "--database-url" not in source
    assert "sha256sum -c" in source
    assert "pg_restore --exit-on-error" in source


def test_disk_check_has_warning_and_critical_thresholds() -> None:
    source = (ROOT / "deploy" / "backup" / "disk-check.sh").read_text(encoding="utf-8")
    assert '"$free_percent" -lt 10' in source
    assert '"$free_percent" -lt 20' in source


def test_restore_drill_compares_source_and_isolated_target() -> None:
    source = (ROOT / "deploy" / "backup" / "drill.sh").read_text(encoding="utf-8")
    assert "DRILL_TARGET_DATABASE_URL" in source
    assert "source_tables" in source and "target_tables" in source
    assert "source_users" in source and "target_users" in source
    assert "source_revision" in source and "target_revision" in source
    assert "source_constraints" in source and "target_constraints" in source
