from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_retired_sqlite_entry_points_are_absent() -> None:
    retired_paths = (
        ROOT / "backend" / "app" / "api_operational" / "router.py",
        ROOT / "scripts" / "apply_db_indexes.py",
        ROOT / "scripts" / "smoke_test_product_flow.py",
        ROOT / "services" / "plan_guard.py",
        ROOT / "legacy_streamlit" / "app.py",
        ROOT / "legacy_streamlit" / "main_streamlit.py",
    )

    assert all(not path.exists() for path in retired_paths)


def test_official_runtime_has_no_retired_entry_point_imports() -> None:
    runtime_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "backend" / "app" / "main.py",
            ROOT / "backend" / "app" / "api" / "v1" / "router.py",
            ROOT / "backend" / "app" / "core" / "celery.py",
        )
    )

    assert "api_operational" not in runtime_sources
    assert "legacy_streamlit" not in runtime_sources
    assert "services.plan_guard" not in runtime_sources
    assert "pg_compat" not in runtime_sources
