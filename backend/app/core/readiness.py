from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from backend.app.core.database import engine
from backend.trading.storage.migrate import LATEST_TRADING_SCHEMA_VERSION


@dataclass(frozen=True)
class SchemaRevisionStatus:
    current: str | None
    expected: str | None
    trading_current: str | None = None
    trading_expected: str = LATEST_TRADING_SCHEMA_VERSION

    @property
    def compatible(self) -> bool:
        return bool(
            self.current
            and self.expected
            and self.current == self.expected
            and self.trading_current == self.trading_expected
        )


@lru_cache(maxsize=1)
def application_schema_head() -> str | None:
    repository_root = Path(__file__).resolve().parents[3]
    config = Config(str(repository_root / "alembic.ini"))
    config.set_main_option("script_location", str(repository_root / "backend" / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


async def schema_revision_status() -> SchemaRevisionStatus:
    expected = application_schema_head()
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num"))
            revisions = [str(value) for value in result.scalars().all()]
            current = revisions[0] if len(revisions) == 1 else ",".join(revisions) or None
            trading_version_table = await connection.execute(
                text("SELECT to_regclass('public.trading_schema_version')")
            )
            if trading_version_table.scalar_one_or_none() is None:
                trading_current = None
            else:
                trading_result = await connection.execute(
                    text("SELECT version FROM trading_schema_version WHERE id = 1")
                )
                trading_current = trading_result.scalar_one_or_none()
    except Exception:
        current = None
        trading_current = None
    return SchemaRevisionStatus(
        current=str(current) if current else None,
        expected=expected,
        trading_current=str(trading_current) if trading_current else None,
    )
