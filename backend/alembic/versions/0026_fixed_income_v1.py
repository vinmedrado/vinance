"""add canonical fixed-income products and investor horizon

Revision ID: 0026_fixed_income_v1
Revises: 0025_intelligence_schema
Create Date: 2026-10-10

The historical fixed-income table stored a display-name identity and was fed
by a provider endpoint that no longer exists. This migration extends that same
canonical table instead of creating a competing investment store. Existing
rows receive an explicitly legacy source identity; no rate, maturity,
liquidity, guarantee or price is fabricated.

Downgrade removes canonical product facts and the investment horizon. It fails
closed when either domain contains data that would be lost.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0026_fixed_income_v1"
down_revision = "0025_intelligence_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_profiles",
        sa.Column("investment_horizon_months", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_financial_profiles_investment_horizon_range",
        "financial_profiles",
        "investment_horizon_months IS NULL OR "
        "investment_horizon_months BETWEEN 1 AND 1200",
    )

    op.add_column(
        "renda_fixa_produtos",
        sa.Column("source_product_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("asset_catalog_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("rate_type", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("purchase_rate", sa.Numeric(precision=18, scale=6), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("redemption_rate", sa.Numeric(precision=18, scale=6), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("unit_price", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column(
            "redemption_unit_price", sa.Numeric(precision=18, scale=2), nullable=True
        ),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("base_unit_price", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("liquidity_type", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("guarantee_type", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("tax_treatment", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'BRL'"),
        ),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column("market_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "renda_fixa_produtos",
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE renda_fixa_produtos
           SET source_product_id = 'legacy:' || id::text,
               purchase_rate = taxa_juros,
               redemption_rate = taxa_total_equiv
         WHERE source_product_id IS NULL
        """
    )
    op.alter_column(
        "renda_fixa_produtos", "source_product_id", nullable=False
    )
    op.alter_column(
        "renda_fixa_produtos", "currency", server_default=None
    )

    op.create_foreign_key(
        "fk_renda_fixa_produtos_asset_catalog",
        "renda_fixa_produtos",
        "asset_catalog",
        ["asset_catalog_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_renda_fixa_produtos_source_product",
        "renda_fixa_produtos",
        ["source", "source_product_id"],
    )
    op.create_check_constraint(
        "ck_renda_fixa_produtos_currency_upper",
        "renda_fixa_produtos",
        "currency = upper(currency)",
    )
    op.create_check_constraint(
        "ck_renda_fixa_produtos_unit_price_positive",
        "renda_fixa_produtos",
        "unit_price IS NULL OR unit_price > 0",
    )
    op.create_check_constraint(
        "ck_renda_fixa_produtos_redemption_price_positive",
        "renda_fixa_produtos",
        "redemption_unit_price IS NULL OR redemption_unit_price > 0",
    )
    op.create_check_constraint(
        "ck_renda_fixa_produtos_base_price_positive",
        "renda_fixa_produtos",
        "base_unit_price IS NULL OR base_unit_price > 0",
    )
    op.create_check_constraint(
        "ck_renda_fixa_produtos_minimum_nonnegative",
        "renda_fixa_produtos",
        "investimento_minimo IS NULL OR investimento_minimo >= 0",
    )
    op.create_index(
        "ix_renda_fixa_produtos_asset_catalog_id",
        "renda_fixa_produtos",
        ["asset_catalog_id"],
    )
    op.create_index(
        "ix_renda_fixa_produtos_market_date",
        "renda_fixa_produtos",
        ["market_date"],
    )
    op.create_index(
        "ix_renda_fixa_produtos_active_market_date",
        "renda_fixa_produtos",
        ["is_active", "market_date"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    product_count = int(
        bind.execute(sa.text("SELECT count(*) FROM renda_fixa_produtos")).scalar_one()
    )
    horizon_count = int(
        bind.execute(
            sa.text(
                "SELECT count(*) FROM financial_profiles "
                "WHERE investment_horizon_months IS NOT NULL"
            )
        ).scalar_one()
    )
    if product_count or horizon_count:
        raise RuntimeError(
            "fixed-income v1 downgrade refused: canonical product or horizon data exists"
        )

    op.drop_index(
        "ix_renda_fixa_produtos_active_market_date",
        table_name="renda_fixa_produtos",
    )
    op.drop_index(
        "ix_renda_fixa_produtos_market_date", table_name="renda_fixa_produtos"
    )
    op.drop_index(
        "ix_renda_fixa_produtos_asset_catalog_id",
        table_name="renda_fixa_produtos",
    )
    op.drop_constraint(
        "ck_renda_fixa_produtos_minimum_nonnegative",
        "renda_fixa_produtos",
        type_="check",
    )
    op.drop_constraint(
        "ck_renda_fixa_produtos_base_price_positive",
        "renda_fixa_produtos",
        type_="check",
    )
    op.drop_constraint(
        "ck_renda_fixa_produtos_redemption_price_positive",
        "renda_fixa_produtos",
        type_="check",
    )
    op.drop_constraint(
        "ck_renda_fixa_produtos_unit_price_positive",
        "renda_fixa_produtos",
        type_="check",
    )
    op.drop_constraint(
        "ck_renda_fixa_produtos_currency_upper",
        "renda_fixa_produtos",
        type_="check",
    )
    op.drop_constraint(
        "uq_renda_fixa_produtos_source_product",
        "renda_fixa_produtos",
        type_="unique",
    )
    op.drop_constraint(
        "fk_renda_fixa_produtos_asset_catalog",
        "renda_fixa_produtos",
        type_="foreignkey",
    )

    for column_name in (
        "source_metadata",
        "market_date",
        "currency",
        "tax_treatment",
        "guarantee_type",
        "liquidity_type",
        "base_unit_price",
        "redemption_unit_price",
        "unit_price",
        "redemption_rate",
        "purchase_rate",
        "rate_type",
        "asset_catalog_id",
        "source_product_id",
    ):
        op.drop_column("renda_fixa_produtos", column_name)

    op.drop_constraint(
        "ck_financial_profiles_investment_horizon_range",
        "financial_profiles",
        type_="check",
    )
    op.drop_column("financial_profiles", "investment_horizon_months")
