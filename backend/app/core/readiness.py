from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from backend.app.core.database import engine


@dataclass(frozen=True)
class SchemaRevisionStatus:
    current: str | None
    expected: str | None

    @property
    def compatible(self) -> bool:
        return bool(self.current and self.expected and self.current == self.expected)


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
    except Exception:
        current = None
    return SchemaRevisionStatus(current=str(current) if current else None, expected=expected)
