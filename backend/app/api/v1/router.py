from __future__ import annotations

from fastapi import APIRouter

from backend.app.auth.router import router as auth_router
from backend.app.financial.router import router as financial_router
from backend.app.financial_state.router import router as financial_state_router
from backend.app.financial_policy.router import router as financial_policy_router
from backend.app.catalog.router import router as catalog_router
from backend.app.market.router import router as market_router
from backend.app.intelligence.router import router as intelligence_router
from backend.app.advisor.router import router as advisor_router
from backend.app.investment_decisions.router import router as investment_decisions_router
from backend.app.investment_performance.router import router as investment_performance_router
from backend.app.investment_alerts.router import router as investment_alerts_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(financial_router)
api_router.include_router(financial_state_router)
api_router.include_router(financial_policy_router)
api_router.include_router(catalog_router)
api_router.include_router(market_router)
api_router.include_router(intelligence_router)
api_router.include_router(advisor_router)
api_router.include_router(investment_decisions_router)
api_router.include_router(investment_performance_router)
api_router.include_router(investment_alerts_router)
