"""ensure crypto intraday append-only index

Revision ID: 0010_crypto_intraday
Revises: 0009_crypto_intraday
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op

revision = "0010_crypto_intraday"
down_revision = "0009_crypto_intraday"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent because some environments may already have received a prior
    # hotfix migration. Crypto must be append-only intraday; the daily unique
    # constraint must not exist.
    op.execute(
        """
        ALTER TABLE cripto_fundamentals
        DROP CONSTRAINT IF EXISTS uq_cripto_fundamentals_coin_id_date
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_cripto_fundamentals_intraday_lookup")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_cripto_fundamentals_coin_id_coletado_em
        ON cripto_fundamentals (coin_id, coletado_em, source)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cripto_fundamentals_coin_id_coletado_em")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_cripto_fundamentals_coin_id_date
        ON cripto_fundamentals (coin_id, date)
        """
    )
