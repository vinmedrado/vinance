from __future__ import annotations

from fastapi import APIRouter
from backend.app.api_operational.routes import health, assets, data, analysis, backtests, optimization

router = APIRouter()
router.include_router(health.router, prefix="/api", tags=["Health"])
router.include_router(assets.router, prefix="/api/assets", tags=["Assets"])
router.include_router(data.router, prefix="/api/data", tags=["Data Layer"])
router.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
router.include_router(backtests.router, prefix="/api/backtests", tags=["Backtests"])
router.include_router(optimization.router, prefix="/api/optimization", tags=["Optimization"])
