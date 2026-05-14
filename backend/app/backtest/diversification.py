from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

# PATCH 13 - Mapa setorial simplificado para reduzir concentração em ativos correlacionados.
# Se um ticker não estiver no mapa, ele entra como "unknown" e não bloqueia a execução.
SECTOR_MAP: Dict[str, str] = {
    # Bancos / financeiros
    'ITUB4':'financials','ITUB3':'financials','BBDC4':'financials','BBDC3':'financials','BBAS3':'financials','SANB11':'financials','BPAC11':'financials','B3SA3':'financials','BBSE3':'financials','IRBR3':'financials','PSSA3':'financials','CXSE3':'financials',
    # Energia / petróleo / utilities
    'PETR4':'energy','PETR3':'energy','PRIO3':'energy','RRRP3':'energy','RECV3':'energy','CSAN3':'energy','UGPA3':'energy','VBBR3':'energy','RAIZ4':'energy',
    'TAEE11':'utilities','EGIE3':'utilities','EQTL3':'utilities','CMIG4':'utilities','CPLE6':'utilities','ELET3':'utilities','ELET6':'utilities','ENGI11':'utilities','CPFE3':'utilities','NEOE3':'utilities',
    # Materiais / mineração / papel / siderurgia
    'VALE3':'materials','GGBR4':'materials','GOAU4':'materials','CSNA3':'materials','USIM5':'materials','SUZB3':'materials','KLBN11':'materials','BRAP4':'materials','CMIN3':'materials','DXCO3':'materials',
    # Consumo / varejo / alimentos
    'ABEV3':'consumer','JBSS3':'consumer','BRFS3':'consumer','MRFG3':'consumer','SMTO3':'consumer','MDIA3':'consumer','ASAI3':'consumer','CRFB3':'consumer','PCAR3':'consumer','MGLU3':'consumer','LREN3':'consumer','AMER3':'consumer','VIIA3':'consumer','NTCO3':'consumer','ARZZ3':'consumer','SOMA3':'consumer','ALPA4':'consumer','RENT3':'consumer','CVCB3':'consumer','PETZ3':'consumer','YDUQ3':'consumer','COGN3':'consumer','ANIM3':'consumer',
    # Saúde
    'HAPV3':'healthcare','RADL3':'healthcare','RDOR3':'healthcare','FLRY3':'healthcare','QUAL3':'healthcare','DASA3':'healthcare','AALR3':'healthcare','ODPV3':'healthcare',
    # Indústria / infraestrutura / transporte
    'WEGE3':'industrials','RAIL3':'industrials','CCRO3':'industrials','ECOR3':'industrials','EMBR3':'industrials','TOTS3':'technology','LWSA3':'technology','MILS3':'industrials','AZUL4':'industrials','GOLL4':'industrials','RAPT4':'industrials',
    # Telecom / real estate
    'VIVT3':'telecom','TIMS3':'telecom','MRVE3':'real_estate','CYRE3':'real_estate','EZTC3':'real_estate','MULT3':'real_estate','IGTI11':'real_estate','BRML3':'real_estate',
}


def ticker_sector(ticker: str) -> str:
    return SECTOR_MAP.get(str(ticker or '').upper().strip(), 'unknown')


class DiversificationPolicy:
    """Política simples de diversificação do PATCH 13.

    - Limita a no máximo 2 ativos por setor quando houver alternativas.
    - Busca manter ao menos min_assets ativos, relaxando apenas quando o universo não permite.
    - Não altera score, apenas limita concentração na seleção final.
    """

    def __init__(self, max_per_sector: int = 2, min_assets: int = 3):
        self.max_per_sector = max(1, int(max_per_sector or 2))
        self.min_assets = max(1, int(min_assets or 3))

    def select(self, ranked_tickers: Sequence[str], top_n: int) -> Tuple[List[str], Dict[str, object]]:
        top_n = max(1, int(top_n or 1))
        selected: List[str] = []
        sector_counts: Dict[str, int] = defaultdict(int)
        excluded: List[Dict[str, object]] = []

        # Primeira passada: aplica limite setorial.
        for ticker in ranked_tickers:
            ticker = str(ticker or '').upper().strip()
            if not ticker or ticker in selected:
                continue
            sector = ticker_sector(ticker)
            if sector != 'unknown' and sector_counts[sector] >= self.max_per_sector:
                excluded.append({'ticker': ticker, 'sector': sector, 'reason': f'limite setorial: máximo {self.max_per_sector} ativos em {sector}'})
                continue
            selected.append(ticker)
            sector_counts[sector] += 1
            if len(selected) >= top_n:
                break

        # Segunda passada: diversificação forçada. Se sobraram poucos ativos por falta
        # de classificação/limite, completa com próximos candidatos até min(top_n, min_assets).
        target_min = min(top_n, self.min_assets)
        relaxed = []
        if len(selected) < target_min:
            for ticker in ranked_tickers:
                ticker = str(ticker or '').upper().strip()
                if not ticker or ticker in selected:
                    continue
                sector = ticker_sector(ticker)
                selected.append(ticker)
                sector_counts[sector] += 1
                relaxed.append({'ticker': ticker, 'sector': sector, 'reason': 'incluído por diversificação forçada: universo filtrado ficou pequeno'})
                if len(selected) >= target_min:
                    break

        concentration = {sector: count for sector, count in sector_counts.items() if count > 0}
        return selected[:top_n], {
            'sector_counts': concentration,
            'excluded_by_sector_limit': excluded,
            'relaxed_inclusions': relaxed,
            'max_per_sector': self.max_per_sector,
            'min_assets': self.min_assets,
        }
