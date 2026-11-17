# Isolated Personal/Couple Finance Release Implementation Plan

> **For Codex:** Execute this plan in the release worktree only. Preserve the original dirty worktree. Commits, push, production migration, and deployment are explicitly prohibited in this task.

**Goal:** Isolate the already implemented PERSONAL/HOUSEHOLD context and audited income/expense transfer capability from the unpublished visual redesign, then prove it against real PostgreSQL and the currently published frontend structure.

**Architecture:** Keep the existing ownership model (`PERSONAL`/`HOUSEHOLD`) and canonical A1→A6 services. Add only the 0028 financial-domain migration, audited transactional transfer service/API, explicit destination/context frontend controls, and focused compatibility styles. Shared frontend files are edited by hunk; redesign navigation, home composition, tokens, and prototype assets remain outside this worktree.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, Alembic, React, TypeScript, TanStack Query, Vitest, Playwright.

---

## Task 1: Establish the isolated baseline

**Files:**
- Create: `docs/superpowers/plans/2026-11-16-isolated-financial-release.md`

- [x] Create sibling worktree from `3ff20f2c4e5e6ef122bfaf1ac3c63367b90490b6`.
- [x] Use branch `release/financial-context-transfers-v1`.
- [x] Confirm original staging remains empty and original changes remain present.
- [x] Confirm release worktree starts clean at the requested commit.

## Task 2: Isolate backend persistence, API, and privacy correction

**Files:**
- Create: `backend/alembic/versions/0028_financial_record_transfers.py`
- Create: `backend/app/financial_state/transfers.py`
- Modify: `backend/app/financial_state/models.py`
- Modify: `backend/app/financial_state/schemas.py`
- Modify: `backend/app/financial_state/router.py`
- Modify: `backend/app/financial_state/service.py`
- Modify: `backend/app/financial/service.py`
- Modify: `backend/tests/test_alembic_fresh_database.py`
- Modify: `backend/tests/test_alembic_schema_ownership.py`
- Create/modify only finance-context tests identified by the audit.

- [ ] Transport only the financial transfer implementation and migration.
- [ ] Add a real-PostgreSQL regression reproducing transfer versus membership revocation/leave lock ordering.
- [ ] Fix the root lock-order issue without weakening ownership checks or transaction atomicity.
- [ ] Preserve all transfer fields, idempotency, audit records, duplicate warnings, and A1→A6 invalidation.
- [ ] Prove that a household owner cannot read or transfer another member's PERSONAL records.

## Task 3: Isolate frontend context and transfer UX

**Files:**
- Create: `frontend/src/features/household/context/FinancialContextProvider.tsx`
- Create: `frontend/src/features/household/components/FinancialContextSwitcher.tsx`
- Create: `frontend/src/features/household/components/SharedFinanceIntro.tsx`
- Create: `frontend/src/features/financial-state/components/OwnershipDestinationField.tsx`
- Create: `frontend/src/features/financial-state/components/TransferFinancialRecordsDialog.tsx`
- Create: `frontend/src/features/financial-state/hooks/useFinancialTransfers.ts`
- Create: `frontend/src/styles/financial-context.css`
- Modify by hunk: `frontend/src/app/main.tsx`
- Modify by hunk: `frontend/src/layout/AppLayout.tsx`
- Modify: `frontend/src/routes/AppRoutes.tsx`
- Modify: `frontend/src/services/financialState.service.ts`
- Modify: `frontend/src/types/financialState.types.ts`
- Modify: `frontend/src/features/household/hooks/useHousehold.ts`
- Modify only relevant finance pages and tests.

- [ ] Keep the published navigation and dashboard composition.
- [ ] Add a persistent, accessible financial-context control compatible with the published shell.
- [ ] Add explicit destination selection to income and expense forms.
- [ ] Add individual and atomic batch transfer review, duplicate warnings, success/error feedback, and form-context safety.
- [ ] Extract only focused feature CSS; do not import redesign-only `shell.css` or `home.css`.

## Task 4: Documentation and scope audit

**Files:**
- Create: `docs/FINANCIAL_CONTEXT_AND_TRANSFERS.md`
- Create/update focused release tests only.

- [ ] Document semantics, authorization, audit trail, duplicate candidates, A1→A6 invalidation, and publication sequence.
- [ ] Compare every release file with the original dirty worktree and base commit.
- [ ] Confirm redesign prototypes, navigation overhaul, home redesign, visual tokens, and Trading changes are absent.
- [ ] Scan the diff for secrets, dumps, screenshots, generated artifacts, and personal data.

## Task 5: Real PostgreSQL and migration verification

- [ ] Run the ten required PostgreSQL tests with `AUTOPILOT_TEST_DATABASE_URL` against the isolated test database.
- [ ] Run 0028 upgrade on a database already at 0027.
- [ ] Run full upgrade to head on an empty PostgreSQL database.
- [ ] Run safe 0028 downgrade and re-upgrade on an isolated database.
- [ ] Verify schema constraints, FKs, indexes, ownership, atomicity, idempotency, concurrency, privacy, audit trail, A1→A6 invalidation, and no double counting.

## Task 6: Frontend and end-to-end verification

- [ ] Run affected backend tests, then the broader safe backend suite required by the release.
- [ ] Run frontend unit tests.
- [ ] Run TypeScript typecheck.
- [ ] Run production frontend build.
- [ ] Run focused Playwright coverage against an isolated/local test environment.
- [ ] Verify desktop/mobile context switch, destination selection, individual/batch transfer, duplicate warning, and privacy behavior.
- [ ] Run `git diff --check`.

## Task 7: Security review and publication plan

- [ ] Review horizontal authorization, household destination validation, audit visibility, PERSONAL snapshot exposure, concurrency, and cache/context invalidation.
- [ ] Record any residual risk as a deploy blocker or accepted limitation.
- [ ] Prepare a no-data-loss plan: verified backup/restore, explicit 0028 production migration, joint backend/frontend deployment, personal-count invariants, smoke tests, and application rollback without destructive schema downgrade.
- [ ] Leave staging empty and make no commit, push, deployment, production migration, or real record transfer.
