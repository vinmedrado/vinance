"""PATCH 9 - backtest engine tables

Revision ID: 20260429_0005
Revises: 20260429_0004
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = '20260429_0005'
down_revision = '20260429_0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('backtest_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('strategy_name', sa.String(120), nullable=False),
        sa.Column('asset_class', sa.String(32), nullable=True),
        sa.Column('start_date', sa.String(10), nullable=False),
        sa.Column('end_date', sa.String(10), nullable=False),
        sa.Column('initial_capital', sa.Float(), nullable=False),
        sa.Column('top_n', sa.Integer(), nullable=True),
        sa.Column('rebalance_frequency', sa.String(32), nullable=True),
        sa.Column('transaction_cost', sa.Float(), nullable=True, server_default='0.001'),
        sa.Column('status', sa.String(32), nullable=True, server_default='created'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('params_json', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
    )
    op.create_table('backtest_trades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('backtest_id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(32), nullable=False),
        sa.Column('action', sa.String(16), nullable=False),
        sa.Column('date', sa.String(10), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('gross_value', sa.Float(), nullable=True),
        sa.Column('transaction_cost', sa.Float(), nullable=True),
        sa.Column('net_value', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_backtest_trades_run', 'backtest_trades', ['backtest_id', 'date'])
    op.create_table('backtest_positions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('backtest_id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(32), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('avg_price', sa.Float(), nullable=False),
        sa.Column('last_price', sa.Float(), nullable=True),
        sa.Column('market_value', sa.Float(), nullable=True),
        sa.Column('last_updated', sa.String(10), nullable=False),
        sa.UniqueConstraint('backtest_id', 'ticker', name='uq_backtest_position'),
    )
    op.create_table('backtest_equity_curve',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('backtest_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.String(10), nullable=False),
        sa.Column('equity_value', sa.Float(), nullable=False),
        sa.Column('cash', sa.Float(), nullable=True),
        sa.Column('positions_value', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('backtest_id', 'date', name='uq_backtest_equity_date'),
    )
    op.create_index('ix_backtest_equity_run', 'backtest_equity_curve', ['backtest_id', 'date'])
    op.create_table('backtest_metrics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('backtest_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('total_return', sa.Float(), nullable=True),
        sa.Column('annual_return', sa.Float(), nullable=True),
        sa.Column('volatility', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('turnover', sa.Float(), nullable=True),
        sa.Column('metrics_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('backtest_metrics')
    op.drop_index('ix_backtest_equity_run', table_name='backtest_equity_curve')
    op.drop_table('backtest_equity_curve')
    op.drop_table('backtest_positions')
    op.drop_index('ix_backtest_trades_run', table_name='backtest_trades')
    op.drop_table('backtest_trades')
    op.drop_table('backtest_runs')
