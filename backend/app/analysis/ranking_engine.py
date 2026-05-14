from __future__ import annotations

from .analysis_repository import save_rankings


def persist_rankings(conn, score_rows: list[dict], top_n: int, calculated_at: str) -> None:
    save_rankings(conn, score_rows, top_n=top_n, calculated_at=calculated_at)
