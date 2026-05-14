class CVMClient:
    """Client isolado para evolução com Dados Abertos CVM de FIIs."""
    def fii_reports(self, ticker: str):
        return {"ticker": ticker.upper(), "reports": [], "source": "CVM_DADOS_ABERTOS", "status": "reserved_for_next_version"}
