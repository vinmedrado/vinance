# VinanceOS Access, PWA and Web Push V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver secure browser bootstrap, invite-only platform access, conservative PWA installation and owner-bound Web Push notifications without opening public signup or caching financial data.

**Architecture:** Add isolated platform-access and notification domains behind a single additive Alembic revision. Extend the existing React shell with focused login/admin/settings flows and a first-party service worker. Keep Cloudflare and e-mail adapters honest about missing external configuration.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, Redis, Celery, React 18, TanStack Query, Vite, first-party service worker, Web Push/VAPID.

**Spec:** `docs/superpowers/specs/2026-11-20-access-pwa-push-design.md`

## Global Constraints

- `PUBLIC_SIGNUP=false`; `INVITE_ONLY=true`.
- Platform admin is independent from household `OWNER`.
- No financial API response or authenticated navigation response is cached by the service worker.
- No Trading changes, no new Trading scheduler and no financial-rule changes.
- Secrets never enter Git, browser bundles, logs or reports.
- Test-first development for every behavior change.

## Review Focus

- Two concurrent bootstrap requests: exactly one administrator is created and the other is rejected.
- A platform invitation cannot be reused, accepted by another e-mail, or accepted after cancellation/expiry.
- Household ownership grants no platform administration and no access to another user's PERSONAL records.
- A browser push endpoint previously owned by user A cannot silently move to user B.
- Offline/update behavior never shows stale financial data as current or discards an unsaved form.

---

### Task 1: Access and notification schema

**Files:**
- Create: `backend/alembic/versions/0029_access_pwa_push_v1.py`
- Create: `backend/app/platform_access/models.py`
- Create: `backend/app/notifications/models.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/test_access_pwa_push_schema.py`

**Interfaces:** Produces platform bootstrap/admin/invitation/reset/audit models and push preference/subscription/delivery models.

- [ ] Write schema tests for tables, constraints, FK indexes, downgrade and empty-database upgrade; run to RED.
- [ ] Implement additive revision `0029_access_pwa_push_v1`; run focused tests to GREEN.
- [ ] Run `alembic check` against isolated PostgreSQL.

### Task 2: Transaction-safe bootstrap and invite-only registration

**Files:**
- Modify: `backend/app/auth/service.py`, `backend/app/auth/schemas.py`, `backend/app/auth/router.py`
- Create: `backend/app/platform_access/service.py`, `schemas.py`, `router.py`, `tokens.py`, `dependencies.py`
- Modify: `backend/app/api/v1/router.py`, `backend/app/core/config.py`
- Test: `backend/tests/test_platform_access_api.py`, `backend/tests/test_platform_access_postgres.py`

**Interfaces:** Produces `/access/capabilities`, `/access/bootstrap`, invitation acceptance and platform-admin account/invitation endpoints.

- [ ] Write failing tests for authorized/unauthorized/concurrent bootstrap, invite lifecycle, role separation and account deactivation.
- [ ] Refactor user creation into an internal no-commit primitive while preserving current callers.
- [ ] Implement bootstrap row lock, one-time token verification, invitation hash/expiry/use-once and audit events.
- [ ] Implement platform-admin authorization and session revocation.
- [ ] Run focused and full auth/household suites.

### Task 3: Honest recovery and external access state

**Files:**
- Create: `backend/app/platform_access/recovery.py`, `cloudflare.py`
- Modify: `backend/app/platform_access/router.py`, `schemas.py`, `backend/app/core/config.py`
- Test: `backend/tests/test_password_recovery.py`, `backend/tests/test_cloudflare_access_contract.py`

**Interfaces:** Produces anti-enumerating recovery request, admin-issued one-time reset links and Cloudflare status `PENDING_AUTHORIZATION` when automation is unavailable.

- [ ] Write failing tests for token expiry/reuse/session revocation/anti-enumeration and forged Cloudflare identity.
- [ ] Implement administrative reset link and optional cryptographic Access JWT validator.
- [ ] Keep e-mail/API delivery disabled and explicit when credentials are absent.

### Task 4: Web Push storage and delivery

**Files:**
- Create: `backend/app/notifications/crypto.py`, `service.py`, `sender.py`, `tasks.py`, `schemas.py`, `router.py`
- Modify: `backend/app/api/v1/router.py`, `backend/app/core/celery.py`, `backend/app/core/config.py`, `requirements.txt`
- Test: `backend/tests/test_web_push_api.py`, `backend/tests/test_web_push_delivery.py`

**Interfaces:** Produces authenticated VAPID public-key, preference, subscribe/unsubscribe and test-send endpoints plus idempotent Celery delivery.

- [ ] Write failing tests for ownership, endpoint collision, encryption, preferences, dedupe, bounded retry and 404/410 deactivation.
- [ ] Implement encrypted subscription storage and owner-derived mutations.
- [ ] Implement sanitized payload allowlist and Celery sender with no scheduled job.
- [ ] Integrate existing household invitation and financial-alert events behind user preferences.

### Task 5: PWA shell and install lifecycle

**Files:**
- Create: `frontend/public/manifest.webmanifest`, `frontend/public/sw.js`, `frontend/public/offline.html`, PWA icon assets
- Create: `frontend/src/features/pwa/*`
- Modify: `frontend/index.html`, `frontend/nginx.conf`, `frontend/src/app/main.tsx`
- Test: `frontend/tests/unit/pwaLifecycle.test.tsx`, `frontend/tests/e2e/pwa.spec.ts`

**Interfaces:** Produces install-state hook, safe SW registration/update and neutral offline behavior.

- [ ] Write failing manifest/service-worker/cache-policy tests.
- [ ] Add identity-consistent icons and manifest metadata.
- [ ] Implement conservative service worker and explicit update action.
- [ ] Add Nginx no-cache rules for manifest/SW and prevent SPA fallback for PWA resources.

### Task 6: Login, administration and notification UI

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`, `frontend/src/routes/AppRoutes.tsx`, `frontend/src/layouts/AppLayout.tsx`
- Create: `frontend/src/pages/PlatformAccessPage.tsx`, `frontend/src/pages/AccountSettingsPage.tsx`, `frontend/src/features/platform-access/*`, `frontend/src/features/notifications/*`
- Modify: `frontend/src/features/auth/*`, scoped styles
- Test: frontend unit tests and Playwright access/PWA/push suites

**Interfaces:** Consumes access and notification APIs; provides bootstrap, invite acceptance, account administration, recovery, install and notification controls.

- [ ] Write failing tests for capability-driven login modes, password confirmation, admin-only navigation and honest pending states.
- [ ] Implement compact accessible forms with inline errors, focus management and clear next steps.
- [ ] Implement explicit push permission gesture and logout subscription cleanup.
- [ ] Run Web Interface Guidelines review and fix findings.

### Task 7: Least-privilege runtime and production configuration

**Files:**
- Modify: `docker-compose.production.yml`, `.env.production.example`, `deploy-production.ps1`
- Create: `deploy/postgres/prepare-runtime-role.sql` or an equivalent idempotent protected operator command and runbook
- Test: compose contract and production dependency tests

**Interfaces:** Separates migration database credentials from runtime credentials and validates required bootstrap/VAPID/encryption settings without exposing them.

- [ ] Write failing compose/config tests for missing secrets and migration/runtime URL separation.
- [ ] Implement least-privilege runtime configuration and idempotent grants.
- [ ] Validate backend/worker/beat with `NOSUPERUSER NOBYPASSRLS` runtime role on isolated PostgreSQL.
- [ ] Document that RLS remains absent rather than claiming database row isolation.

### Task 8: Full verification and controlled release

**Files:**
- Create/modify relevant tests and `docs/ACCESS_PWA_PUSH_V1.md`

- [ ] Run backend suites, isolated PostgreSQL migration upgrade/downgrade/fresh database and concurrency tests.
- [ ] Run frontend unit, typecheck, build and Playwright desktop/mobile/PWA checks.
- [ ] Verify no secrets/source maps/sensitive cached responses and run `git diff --check`.
- [ ] Generate VAPID/bootstrap/encryption secrets only into ignored protected production configuration; do not print them.
- [ ] Stop before deploy if Cloudflare/bootstrap/VAPID/privacy/runtime-role gates fail.
- [ ] If gates pass, validate compose, apply only revision 0029 explicitly, deploy backend+frontend, smoke-test, commit and push without force.
