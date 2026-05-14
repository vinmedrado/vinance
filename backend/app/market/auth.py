"""Integração obrigatória com autenticação existente do FinanceOS.

Ajuste este import caso o projeto use outro caminho, mas não crie fallback inseguro.
"""
try:
    from backend.app.auth import get_current_user  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Não foi possível importar app.auth.get_current_user. "
        "Ajuste backend/app/market/auth.py para apontar para a dependência JWT real do FinanceOS."
    ) from exc
