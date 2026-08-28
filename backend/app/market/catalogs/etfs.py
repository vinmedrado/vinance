from __future__ import annotations

from backend.app.market.catalogs.loader import load_catalog

_FALLBACK = ['AGRI11', 'BBOI11', 'BBOV11', 'BITH11', 'BOVA11', 'BOVB11', 'BOVS11', 'BOVV11', 'DIVO11', 'ECOO11', 'ESGB11', 'FIND11', 'GENB11', 'GOLD11', 'GOVE11', 'HASH11', 'ISUS11', 'IVVB11', 'MATB11', 'MILA11', 'NASD11', 'NFTS11', 'PIBB11', 'QBTC11', 'QDFI11', 'QETH11', 'SMAL11', 'SPXB11', 'SPXI11', 'TECK11', 'TRIG11', 'USTK11', 'WRLD11', 'XBOV11', 'XFIX11', 'XINA11']

ETFS = load_catalog("etfs", _FALLBACK)
