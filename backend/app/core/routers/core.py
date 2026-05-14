from __future__ import annotations

from fastapi import APIRouter, Depends
from backend.app.shared.auth import AuthenticatedUser, require_authenticated_user
from backend.app.core.services.personal_finance import get_core_summary

router = APIRouter(prefix="/core", tags=["Core Finance"])

@router.get("/summary")
def summary(auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return get_core_summary()
