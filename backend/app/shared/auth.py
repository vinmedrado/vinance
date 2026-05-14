from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status

try:
    from backend.app.auth import get_current_user  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Não foi possível importar app.auth.get_current_user. "
        "Aponte app/shared/auth.py para a dependência JWT real do FinanceOS."
    ) from exc


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: int
    raw: Any


def _extract_user_id(current_user: Any) -> int:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não autenticado")

    raw_id: Any = None
    if isinstance(current_user, dict):
        raw_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
    else:
        raw_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", None) or getattr(current_user, "sub", None)

    if raw_id in (None, ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem user_id válido")

    try:
        user_id = int(raw_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_id inválido") from exc

    if user_id <= 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_id inválido")
    return user_id


def require_authenticated_user(current_user: Any = Depends(get_current_user)) -> AuthenticatedUser:
    """Dependency única de autenticação para todos os módulos novos.

    Garante que user_id nunca seja None e centraliza o isolamento por usuário.
    Toda rota deve receber AuthenticatedUser e filtrar/gravar dados usando auth.user_id.
    """
    return AuthenticatedUser(user_id=_extract_user_id(current_user), raw=current_user)


def require_user_id(auth: AuthenticatedUser = Depends(require_authenticated_user)) -> int:
    return auth.user_id
