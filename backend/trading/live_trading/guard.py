from __future__ import annotations


def assert_live_trading_disabled() -> None:
    raise RuntimeError(
        "Trading real não está implementado. Use PAPER_ONLY até concluir validação, segurança e revisão manual."
    )
