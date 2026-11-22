from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.platform_access.models import PlatformAdmin


async def is_platform_admin(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(
        select(PlatformAdmin.user_id).where(
            PlatformAdmin.user_id == user_id,
            PlatformAdmin.status == "ACTIVE",
        )
    )
    return result.scalar_one_or_none() is not None


async def require_platform_admin(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not await is_platform_admin(session, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform administrator required")
    return current_user
