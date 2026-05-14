"""Central registry for FinanceOS SQLAlchemy models.

This module does not define new tables. It only imports every model class so
Alembic, validation scripts and the application share the same metadata source.
"""

from backend.app.market.models import (  # noqa: F401
    Asset,
    AssetFundamental,
    AssetPrice,
    InvestmentAnalysisHistory,
    InvestmentOpportunity,
    MacroIndicator,
    MarketIndex,
    UserInvestmentPreference,
)
from backend.app.investment.models import (  # noqa: F401
    AssetDividend,
    DataSyncLog,
    FixedIncomeProduct,
    PortfolioPosition,
)
from backend.app.financing.models import (  # noqa: F401
    FinancingHistory,
    FinancingPreset,
    FinancingSimulation,
)
from backend.app.financial.models import (  # noqa: F401
    FinancialDecisionHistory,
    FinancialGoal,
    FinancialMonthlyReport,
    FinancialUserProfile,
    MonthlyFinancialTarget,
)

from backend.app.erp.models import (  # noqa: F401
    ERPAccount, ERPAlert, ERPBudget, ERPCard, ERPCategory, ERPExpense, ERPIncome, ERPPlannedInvestment,
)

from backend.app.enterprise.models import (  # noqa: F401
    Organization, EnterpriseUser, Role, Permission, RolePermission, OrganizationMember, Subscription,
    TenantSetting, UserSession, RefreshToken, PasswordResetToken, EmailVerificationToken, AuditLog, EnterpriseJob,
)

from backend.app.intelligence.models import FinancialProfile, FinancialGoalEngine, IntelligentRecommendationSnapshot, BudgetAdvisorSnapshot  # noqa: F401
