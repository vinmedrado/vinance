from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.app.auth.models import User  # noqa: F401
from backend.app.capital_allocation.models import CapitalAllocationDecision  # noqa: F401
from backend.app.investment_orchestrator.models import (  # noqa: F401
    InvestmentOrchestrationDecision,
)
from backend.app.financial.models import Expense, FinancialProfile, Income  # noqa: F401
from backend.app.financial_policy.models import FinancialPolicyDecision  # noqa: F401
from backend.app.financial_state.models import (  # noqa: F401
    FinancialGoal,
    FinancialLiability,
    FinancialStateSnapshot,
    Household,
    HouseholdMember,
    OwnedAsset,
)
from backend.app.catalog.models import AssetCatalog  # noqa: F401
from backend.app.market.models.acoes import AcaoFundamental  # noqa
from backend.app.market.models.bdr import BdrFundamental  # noqa
from backend.app.market.models.cripto import CriptoFundamental  # noqa
from backend.app.market.models.etf import EtfFundamental  # noqa
from backend.app.market.models.fii import FiiFundamental  # noqa
from backend.app.market.models.macro import MacroIndicator  # noqa: F401
from backend.app.market.models.prices import AssetPrice  # noqa: F401
from backend.app.market.models.renda_fixa import RendaFixaProduto  # noqa
from backend.app.market.models.sync_log import SyncLog  # noqa: F401
from backend.app.market.models.sync_error_log import SyncErrorLog  # noqa: F401
from backend.app.intelligence.asset_score_model import AssetScore  # noqa: F401
from backend.app.intelligence.investment_recommendation_model import InvestmentRecommendation  # noqa: F401
from backend.app.intelligence.models import (  # noqa: F401
    AcaoMLFeature,
    BdrMLFeature,
    CriptoMLFeature,
    EtfMLFeature,
    FiiMLFeature,
)
from backend.app.intelligence.recommendation_guardrail_model import AssetRecommendationGuardrail  # noqa: F401
from backend.app.intelligence.asset_trend_signal_model import AssetTrendSignal  # noqa: F401
from backend.app.investment_decisions.models import InvestmentDecisionAudit  # noqa: F401
from backend.app.investment_performance.models import InvestmentDecisionPerformance  # noqa: F401
from backend.app.investment_alerts.models import (  # noqa: F401
    InvestmentAlert,
    InvestmentAlertState,
    InvestmentAlertSubscription,
)
from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.alembic.schema_ownership import include_name

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
