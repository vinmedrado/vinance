from __future__ import annotations

from datetime import date

import pytest

from backend.app.financial import service


class _ScalarResult:
    def scalar_one(self) -> int:
        return 0


class _CapturingSession:
    statement = None

    async def execute(self, statement):
        self.statement = statement
        return _ScalarResult()


@pytest.mark.asyncio
async def test_personal_diagnosis_excludes_expenses_moved_to_shared_household() -> None:
    session = _CapturingSession()

    await service._sum_user_expenses_30d(
        session,  # type: ignore[arg-type]
        user_id=17,
        today=date(2026, 11, 4),
    )

    assert session.statement is not None
    sql = str(session.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "JOIN households" in sql
    assert "expenses.ownership_scope = 'PERSONAL'" in sql
    assert "households.household_type = 'PERSONAL'" in sql
    assert "households.status = 'ACTIVE'" in sql
