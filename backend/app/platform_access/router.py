from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.http_security import validate_cookie_origin
from backend.app.auth.models import User
from backend.app.auth.normalization import normalize_email
from backend.app.auth.rate_limit import enforce_auth_rate_limit
from backend.app.auth.router import set_refresh_cookie
from backend.app.auth.schemas import TokenResponse
from backend.app.auth.sessions import issue_session
from backend.app.core.config import settings
from backend.app.core.database import get_session
from backend.app.platform_access.dependencies import is_platform_admin, require_platform_admin
from backend.app.platform_access.schemas import (
    AccessActionResult,
    AccessCapabilities,
    BootstrapRequest,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationIssued,
    InvitationRead,
    ManualPasswordResetIssued,
    PasswordRecoveryAccepted,
    PasswordRecoveryRequest,
    PasswordResetComplete,
    PlatformAccessProfile,
    PlatformUserRead,
)
from backend.app.platform_access.service import (
    accept_invitation,
    access_capabilities,
    bootstrap_platform,
    cancel_invitation,
    complete_password_reset,
    create_invitation,
    issue_manual_password_reset,
    list_invitations,
    list_platform_users,
    resend_invitation,
    set_user_active,
)


router = APIRouter(prefix="/access", tags=["platform-access"])


def _identifier(request: Request, subject: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}:{subject}"


def _correlation_id(request: Request) -> str | None:
    value = getattr(request.state, "correlation_id", None)
    return str(value) if value else None


def _issued(invitation, raw_token: str) -> InvitationIssued:
    return InvitationIssued(
        invitation=invitation,
        registration_path=f"/access/invitation#token={raw_token}",
        manual_link_required=True,
        message=(
            "Convite criado — autorização de acesso no Cloudflare e entrega manual pendentes."
            if invitation.cloudflare_access_status == "PENDING_AUTHORIZATION"
            else "Convite criado. Compartilhe o link por um canal confiável."
        ),
    )


@router.get("/capabilities", response_model=AccessCapabilities)
async def capabilities(session: AsyncSession = Depends(get_session)) -> AccessCapabilities:
    return AccessCapabilities(**(await access_capabilities(session)))


@router.post("/bootstrap", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap(
    payload: BootstrapRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    validate_cookie_origin(request)
    await enforce_auth_rate_limit(
        "platform-bootstrap",
        _identifier(request, normalize_email(str(payload.email))),
        settings.platform_access_rate_limit,
    )
    user = await bootstrap_platform(session, payload, correlation_id=_correlation_id(request))
    access_token, refresh_token = await issue_session(session, user)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, user=user)


@router.post("/invitations/accept", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def invitation_accept(
    payload: InvitationAcceptRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    validate_cookie_origin(request)
    await enforce_auth_rate_limit(
        "platform-invitation-accept",
        _identifier(request, normalize_email(str(payload.email))),
        settings.platform_access_rate_limit,
    )
    user = await accept_invitation(session, payload, correlation_id=_correlation_id(request))
    access_token, refresh_token = await issue_session(session, user)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, user=user)


@router.post(
    "/password-recovery/request",
    response_model=PasswordRecoveryAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def password_recovery_request(
    payload: PasswordRecoveryRequest,
    request: Request,
) -> PasswordRecoveryAccepted:
    validate_cookie_origin(request)
    await enforce_auth_rate_limit(
        "password-recovery-request",
        _identifier(request, normalize_email(str(payload.email))),
        settings.platform_access_rate_limit,
    )
    # Deliberately anti-enumerating. A provider will be wired only when a
    # reliable delivery channel is configured; this endpoint never fabricates
    # a successful email delivery.
    return PasswordRecoveryAccepted(
        delivery_available=False,
        message="A recuperação automática ainda não possui canal de entrega. Solicite um link ao administrador.",
    )


@router.post("/password-recovery/complete", response_model=AccessActionResult)
async def password_recovery_complete(
    payload: PasswordResetComplete,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AccessActionResult:
    validate_cookie_origin(request)
    await enforce_auth_rate_limit(
        "password-recovery-complete",
        _identifier(request, "token"),
        settings.platform_access_rate_limit,
    )
    await complete_password_reset(
        session,
        token=payload.token,
        new_password=payload.new_password,
        correlation_id=_correlation_id(request),
    )
    return AccessActionResult(status="COMPLETED", message="Senha redefinida. Entre novamente.")


@router.get("/profile", response_model=PlatformAccessProfile)
async def platform_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PlatformAccessProfile:
    return PlatformAccessProfile(is_platform_admin=await is_platform_admin(session, current_user.id))


@router.get("/admin/users", response_model=list[PlatformUserRead])
async def admin_users(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[PlatformUserRead]:
    return await list_platform_users(session)


@router.get("/admin/invitations", response_model=list[InvitationRead])
async def admin_invitations(
    _: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[InvitationRead]:
    return await list_invitations(session)


@router.post("/admin/invitations", response_model=InvitationIssued, status_code=201)
async def admin_create_invitation(
    payload: InvitationCreateRequest,
    request: Request,
    current_user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> InvitationIssued:
    await enforce_auth_rate_limit(
        "platform-invitation-create",
        _identifier(request, str(current_user.id)),
        settings.invitation_rate_limit,
    )
    invitation, raw_token = await create_invitation(
        session,
        actor_user_id=current_user.id,
        email=str(payload.email),
        correlation_id=_correlation_id(request),
    )
    return _issued(invitation, raw_token)


@router.post("/admin/invitations/{invitation_id}/resend", response_model=InvitationIssued)
async def admin_resend_invitation(
    invitation_id: str,
    request: Request,
    current_user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> InvitationIssued:
    await enforce_auth_rate_limit(
        "platform-invitation-resend",
        _identifier(request, str(current_user.id)),
        settings.invitation_rate_limit,
    )
    invitation, raw_token = await resend_invitation(
        session,
        invitation_id,
        actor_user_id=current_user.id,
        correlation_id=_correlation_id(request),
    )
    return _issued(invitation, raw_token)


@router.post("/admin/invitations/{invitation_id}/cancel", response_model=InvitationRead)
async def admin_cancel_invitation(
    invitation_id: str,
    request: Request,
    current_user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> InvitationRead:
    await enforce_auth_rate_limit(
        "platform-invitation-cancel",
        _identifier(request, str(current_user.id)),
        settings.invitation_rate_limit,
    )
    return await cancel_invitation(
        session,
        invitation_id,
        actor_user_id=current_user.id,
        correlation_id=_correlation_id(request),
    )


@router.post("/admin/users/{user_id}/deactivate", response_model=AccessActionResult)
async def admin_deactivate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AccessActionResult:
    await enforce_auth_rate_limit(
        "platform-user-deactivate",
        _identifier(request, str(current_user.id)),
        settings.platform_access_rate_limit,
    )
    await set_user_active(
        session,
        actor_user_id=current_user.id,
        target_user_id=user_id,
        active=False,
        correlation_id=_correlation_id(request),
    )
    return AccessActionResult(status="INACTIVE", message="Acesso desativado e sessões revogadas.")


@router.post("/admin/users/{user_id}/activate", response_model=AccessActionResult)
async def admin_activate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AccessActionResult:
    await enforce_auth_rate_limit(
        "platform-user-activate",
        _identifier(request, str(current_user.id)),
        settings.platform_access_rate_limit,
    )
    await set_user_active(
        session,
        actor_user_id=current_user.id,
        target_user_id=user_id,
        active=True,
        correlation_id=_correlation_id(request),
    )
    return AccessActionResult(status="ACTIVE", message="Acesso reativado.")


@router.post("/admin/users/{user_id}/password-reset-link", response_model=ManualPasswordResetIssued)
async def admin_password_reset_link(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> ManualPasswordResetIssued:
    await enforce_auth_rate_limit(
        "platform-password-reset-link",
        _identifier(request, str(current_user.id)),
        settings.platform_access_rate_limit,
    )
    raw_token, expires_at = await issue_manual_password_reset(
        session,
        actor_user_id=current_user.id,
        target_user_id=user_id,
        correlation_id=_correlation_id(request),
    )
    return ManualPasswordResetIssued(
        reset_path=f"/access/reset#token={raw_token}",
        expires_at=expires_at,
        message="Link de uso único gerado. Compartilhe por um canal confiável.",
    )
