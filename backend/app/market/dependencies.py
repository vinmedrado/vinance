from __future__ import annotations

from backend.app.shared.auth import AuthenticatedUser, require_authenticated_user, require_user_id


def extract_user_id(current_user: object) -> int:
    """Compatibilidade com imports antigos.

    Novas rotas devem usar require_authenticated_user/require_user_id.
    """
    if isinstance(current_user, AuthenticatedUser):
        return current_user.user_id
    from backend.app.shared.auth import _extract_user_id
    return _extract_user_id(current_user)
