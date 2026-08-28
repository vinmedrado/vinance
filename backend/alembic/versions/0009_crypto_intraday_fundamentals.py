"""make crypto fundamentals intraday append-only

Revision ID: 0009_crypto_intraday
Revises: 0008_create_sync_error_log
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_crypto_intraday"
down_revision = "0008_create_sync_error_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crypto is a 24/7 market. The old daily uniqueness collapsed all snapshots
    # from the same day into one row. Keep date for reporting, but make history
    # append-only by indexing the real collection timestamp.
    op.drop_constraint(
        "uq_cripto_fundamentals_coin_id_date",
        "cripto_fundamentals",
        type_="unique",
    )
    op.create_index(
        "ix_cripto_fundamentals_coletado_em",
        "cripto_fundamentals",
        ["coletado_em"],
    )
    op.create_index(
        "ix_cripto_fundamentals_coin_id_coletado_em",
        "cripto_fundamentals",
        ["coin_id", "coletado_em", "source"],
    )


def downgrade() -> None:
    op.drop_index("ix_cripto_fundamentals_coin_id_coletado_em", table_name="cripto_fundamentals")
    op.drop_index("ix_cripto_fundamentals_coletado_em", table_name="cripto_fundamentals")
    op.create_unique_constraint(
        "uq_cripto_fundamentals_coin_id_date",
        "cripto_fundamentals",
        ["coin_id", "date"],
    )
