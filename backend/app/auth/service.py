from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.models import User
from backend.app.auth.security import get_password_hash, verify_password
from backend.app.auth.schemas import UserCreate
from backend.app.financial_state.models import Household, HouseholdMember


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, payload: UserCreate) -> User:
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
    )
    session.add(user)
    await session.flush()
    household = Household(
        name=f"{payload.full_name or payload.email} — pessoal",
        household_type="PERSONAL",
        created_by_user_id=user.id,
        status="ACTIVE",
    )
    session.add(household)
    await session.flush()
    session.add(
        HouseholdMember(
            household_id=household.id,
            user_id=user.id,
            role="OWNER",
            status="ACTIVE",
            is_default=True,
        )
    )
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return None
    return user
