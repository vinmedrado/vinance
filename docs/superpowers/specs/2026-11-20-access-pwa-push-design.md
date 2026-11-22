# VinanceOS Access, PWA and Web Push V1 Design

## Intent

Allow the VinanceOS owner to bootstrap the first platform administrator in the browser, invite additional isolated users, manage platform access, install the application as a conservative PWA, and opt in to Web Push notifications without opening public registration or weakening financial privacy.

## Goals

- Keep `REGISTRATION_ENABLED=false` and introduce a separate `INVITE_ONLY` access contract.
- Separate platform administration from household ownership.
- Make initial bootstrap atomic, one-time, browser-based, and protected by either a verified Cloudflare Access identity or a high-entropy one-time bootstrap credential.
- Create platform invitations and password-reset credentials as hashed, expiring, single-use tokens.
- Make the PWA installable without persistently caching authenticated API responses or personal financial data.
- Store Web Push subscriptions owner-only, encrypted at rest, with idempotent delivery and bounded retries.
- Reuse canonical household invitations and investment alerts as notification sources without changing Trading or financial rules.

## Non-goals

- Public anonymous signup.
- Automatic broad Cloudflare policy changes.
- Pretending e-mail delivery exists when no provider is configured.
- Offline access to financial data.
- Trading notifications, mass notifications, or a new scheduler.
- Global visual redesign.

## Constraints

- The base is published commit `801342c14ff16fa68a5977774b36f857bfe3848e` in an isolated worktree.
- Existing dirty visual worktree remains untouched.
- New schema belongs to main Alembic after `0028`; Trading external schema is unchanged.
- Tokens, VAPID private key, subscription encryption key, Cloudflare credentials and SMTP credentials never enter Git or browser bundles.
- A household `OWNER` is never automatically a platform administrator.
- Push permission is requested only after an explicit user gesture.

## Approaches considered

### 1. Full Cloudflare API and SMTP automation

Best end-to-end experience, but cannot be made operational without scoped Cloudflare and e-mail credentials that do not currently exist. It remains an optional adapter, not a release gate for the local invite workflow.

### 2. Secure local bootstrap plus invite links, with external-state honesty — selected

The first administrator uses a one-time high-entropy credential in the browser. Platform invitations and administrative password-reset links are single-use and displayed only once for secure out-of-band delivery. Cloudflare status is explicitly `PENDING_AUTHORIZATION` until an operator adds the invitee to Access. If SMTP is later configured, the same token contracts can be delivered by e-mail without changing authorization.

This is the only approach that is secure and actually operable with the current infrastructure.

### 3. Temporarily enable the legacy public register route

Rejected. It conflicts with invite-only access and would make an anonymous visitor eligible to register.

## Backend architecture

- `backend/app/platform_access/`: platform roles, bootstrap, invitation, account administration, recovery and audit services/routers.
- `backend/app/notifications/`: encrypted Web Push subscriptions, user preferences, delivery outbox, sender adapter and Celery task.
- `backend/alembic/versions/0029_access_pwa_push_v1.py`: additive schema and constraints.
- Existing `create_user` gains an internal transaction-safe primitive; public behavior stays compatible.
- Bootstrap locks a singleton state row and creates user, PERSONAL household, platform admin and audit event in one transaction.
- Invitation acceptance locks the invitation row, verifies hash/expiry/e-mail/state, creates the isolated user and consumes the token atomically.
- Account deactivation revokes active sessions. The last active platform admin cannot deactivate itself.
- Password recovery is available through a one-time administrative link while SMTP delivery is unavailable. The public request remains anti-enumeration and never claims delivery when disabled.

## Database security

- New foreign keys are indexed; states are constrained; raw tokens are never stored.
- Web Push subscription payloads are encrypted with a dedicated server-only Fernet key; endpoint hashes support uniqueness and revocation.
- Runtime database least privilege is prepared as an explicit operational gate. RLS is not claimed: current architecture does not set a trusted per-request database identity, so enabling policies blindly would be unsafe.

## Frontend architecture

- Login exposes Entrar, Configuração inicial, Aceitar convite and Recuperar acesso only when backend capabilities allow the corresponding flow.
- `/admin/access` provides platform invitations and user access management to platform admins only.
- `/account/settings` provides PWA installation and notification controls.
- PWA shell uses a small first-party service worker. `/api/`, auth, Trading and financial navigation responses are network-only; only versioned static assets and a neutral offline page are cacheable.
- Android uses `beforeinstallprompt`; iOS receives truthful Add to Home Screen instructions.
- Push subscription ownership is derived from the authenticated session. Logout attempts to unsubscribe the current installation before clearing the session.

## Web Push events

- Explicit test notification.
- Existing household invitation, when the recipient already has an account and enabled that category.
- Existing persisted financial alert, with generic lock-screen copy and no balance/value details.
- Every delivery has an idempotency key; 404/410 deactivates the endpoint.

## External dependencies and states

- Cloudflare API provisioning is optional. Without scoped credentials, invitations show `Autorização de acesso pendente` and no claim of external accessibility is made.
- SMTP is optional. Without it, self-service e-mail recovery and automated invitation delivery remain disabled; secure one-time admin links remain available.
- iPhone push is only marked device-validated after a real installed-device test.

## Release gates

- PostgreSQL migration upgrade/downgrade and concurrency tests pass on isolated PostgreSQL.
- Auth, invitation, ownership, admin authorization and anti-enumeration tests pass.
- Manifest, service worker, no-sensitive-cache and notification UI tests pass.
- Web Push live delivery is tested only when VAPID and a real push service endpoint are available.
- Production deploy is blocked if bootstrap credentials, VAPID, subscription encryption or schema compatibility are incomplete.
- Commit/push occur only after post-deploy smoke tests; otherwise the branch is preserved without false success.
