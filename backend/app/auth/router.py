from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.http_security import validate_cookie_origin
from backend.app.auth.models import User
from backend.app.auth.normalization import normalize_email
from backend.app.auth.rate_limit import enforce_auth_rate_limit
from backend.app.auth.schemas import PasswordChange, TokenResponse, UserCreate, UserLogin, UserRead
from backend.app.auth.service import authenticate_user, change_user_password, create_user, get_user_by_email
from backend.app.auth.sessions import issue_session, revoke_by_refresh_token, rotate_session
from backend.app.core.config import settings
from backend.app.core.database import get_session

router = APIRouter(tags=["auth"])


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
        path=settings.refresh_cookie_path,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _request_identifier(request: Request, subject: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}:{subject}"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    validate_cookie_origin(request)
    if not settings.registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled")
    await enforce_auth_rate_limit(
        "register", _request_identifier(request, normalize_email(str(payload.email))), settings.register_rate_limit
    )
    existing_user = await get_user_by_email(session, payload.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    user = await create_user(session, payload)
    access_token, refresh_token = await issue_session(session, user)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, user=user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    validate_cookie_origin(request)
    normalized_email = normalize_email(str(payload.email))
    client = request.client.host if request.client else "unknown"
    await enforce_auth_rate_limit(
        "login-ip", client, settings.login_ip_rate_limit
    )
    await enforce_auth_rate_limit(
        "login-identity", normalized_email, settings.login_rate_limit
    )
    user = await authenticate_user(session, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token, refresh_token = await issue_session(session, user)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, user=user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    validate_cookie_origin(request)
    await enforce_auth_rate_limit(
        "refresh", _request_identifier(request, "cookie"), settings.refresh_rate_limit
    )
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    rotated = await rotate_session(session, refresh_token) if refresh_token else None
    if rotated is None:
        clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    user, access_token, replacement = rotated
    set_refresh_cookie(response, replacement)
    return TokenResponse(access_token=access_token, user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: AsyncSession = Depends(get_session)) -> Response:
    validate_cookie_origin(request)
    installation_id = request.headers.get("x-vinance-installation-id")
    if installation_id and not re.fullmatch(r"[A-Za-z0-9._:-]{8,64}", installation_id):
        installation_id = None
    user_id = await revoke_by_refresh_token(
        session, request.cookies.get(settings.refresh_cookie_name)
    )
    if user_id is not None and installation_id:
        # Keep the server-side subscription detached even if the browser's
        # best-effort unsubscribe failed during logout.
        from backend.app.notifications.service import revoke_installation

        await revoke_installation(
            session, user_id=user_id, installation_id=installation_id
        )
    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await enforce_auth_rate_limit(
        "password-change",
        _request_identifier(request, current_user.email),
        settings.password_change_rate_limit,
    )
    changed = await change_user_password(session, current_user, payload.current_password, payload.new_password)
    if not changed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is invalid")
    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
