"""Simple, explicit versions attached to every immutable decision snapshot."""

from backend.app.intelligence.services.asset_score_service import SCORE_SOURCE
from backend.app.intelligence.services.recommendation_guardrail_service import GUARDRAIL_SOURCE
from backend.app.intelligence.services.trend_signal_service import TREND_SOURCE

RECOMMENDATION_ENGINE_VERSION = "budget-advisor-v1"
RULE_VERSION = "investment-decision-presentation-v1"
SNAPSHOT_SCHEMA_VERSION = "investment-decision-audit-v1"
SCORE_VERSION = SCORE_SOURCE
GUARDRAIL_VERSION = GUARDRAIL_SOURCE
TREND_VERSION = TREND_SOURCE
