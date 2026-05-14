from sqlalchemy.orm import Session
from backend.app.market.models import InvestmentOpportunity, InvestmentAnalysisHistory
from backend.app.market.services.market_data_service import MarketDataService
from backend.app.market.services.opportunity_engine import rank_opportunities
from backend.app.market.services.allocation_engine import allocation_for_profile

DISCLAIMER = "Análise educacional e quantitativa. Não é promessa de lucro, recomendação individual de compra/venda ou consultoria de investimento. Dados podem estar incompletos ou atrasados."

class RadarService:
    def __init__(self, db: Session):
        self.db = db; self.market = MarketDataService()

    def run_radar(self, *, user_id, amount: float, risk_profile: str, symbols=None, crypto_ids=None):
        symbols = symbols or self.market.default_symbols(); crypto_ids = crypto_ids or self.market.default_crypto_ids()
        macro_context = self.market.get_macro_context()
        b3_quotes = self.market.get_b3_quotes(symbols)
        crypto_items = self.market.get_crypto_markets(crypto_ids)
        crypto_price_map = {}
        for coin_id in crypto_ids:
            try: crypto_price_map[coin_id] = [p["close"] for p in self.market.get_crypto_chart_prices(coin_id, 365)]
            except Exception: crypto_price_map[coin_id] = []
        opportunities = rank_opportunities(b3_quotes, crypto_items, crypto_price_map, risk_profile, macro_context)
        allocation = allocation_for_profile(amount, risk_profile, macro_context)
        for opp in opportunities[:25]:
            self.db.add(InvestmentOpportunity(user_id=user_id, symbol=opp["symbol"], asset_class=opp["asset_class"], score=opp["score"], classification=opp["classification"], metrics_json=opp["metrics"], rationale=opp["rationale"]))
        self.db.add(InvestmentAnalysisHistory(user_id=user_id, amount=amount, risk_profile=risk_profile, allocation_json=allocation, top_opportunities_json=opportunities[:20], macro_context_json=macro_context))
        self.db.commit()
        return {"amount": amount, "risk_profile": risk_profile, "allocation": allocation, "macro_context": macro_context, "opportunities": opportunities[:30], "disclaimer": DISCLAIMER}
