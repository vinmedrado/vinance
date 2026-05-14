from backend.app.market.services.market_data_service import MarketDataService

def daily_prices_job():
    service = MarketDataService(); return service.get_b3_quotes(service.default_symbols())
def weekly_fundamentals_job():
    service = MarketDataService(); return service.get_b3_quotes(service.default_symbols())
def monthly_macro_job():
    return MarketDataService().get_macro_context()
