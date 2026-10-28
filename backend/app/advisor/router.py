from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.advisor.schemas import AdvisorChatRequest, AdvisorChatResponse
from backend.app.advisor import service
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.auth.rate_limit import enforce_auth_rate_limit
from backend.app.core.config import settings
from backend.app.core.database import get_session

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post("/chat", response_model=AdvisorChatResponse)
async def advisor_chat(
    payload: AdvisorChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await enforce_auth_rate_limit(
        "advisor-chat",
        str(current_user.id),
        settings.advisor_chat_rate_limit,
        unavailable_detail="Assistente temporariamente indisponível",
        exceeded_detail="Muitas perguntas em pouco tempo; tente novamente em instantes",
    )
    try:
        return await service.chat(session, user_id=current_user.id, message=payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
