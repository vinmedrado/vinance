from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MarketCode = Literal["fii", "acoes", "etf", "bdr", "cripto", "renda_fixa"]
MacroCode = Literal["SELIC", "IPCA", "CDI"]


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    return ticker


def normalize_market(value: str) -> str:
    market = value.strip().lower()
    allowed = {"fii", "acoes", "etf", "bdr", "cripto", "renda_fixa"}
    if market not in allowed:
        raise ValueError("invalid market")
    return market


class AssetPriceIn(BaseModel):
    ticker: str
    market: MarketCode
    date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal = Field(gt=0)
    volume: Decimal | None = Field(default=None, ge=0)
    source: str

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, value: str) -> str:
        return normalize_ticker(value)

    @field_validator("market")
    @classmethod
    def _market(cls, value: str) -> str:
        return normalize_market(value)

    @field_validator("source")
    @classmethod
    def _source(cls, value: str) -> str:
        source = value.strip().lower()
        if not source:
            raise ValueError("source is required")
        return source


class AssetPriceRead(AssetPriceIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class MacroIndicatorIn(BaseModel):
    code: MacroCode
    name: str
    date: date
    value: Decimal
    source: str

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("source")
    @classmethod
    def _source(cls, value: str) -> str:
        source = value.strip().lower()
        if not source:
            raise ValueError("source is required")
        return source


class MacroIndicatorRead(MacroIndicatorIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class RendaFixaProdutoIn(BaseModel):
    nome: str
    emissor: str | None = None
    tipo: str
    indexador: str | None = None
    taxa_juros: Decimal | None = None
    taxa_total_equiv: Decimal | None = None
    vencimento: date | None = None
    liquidez_dias: int | None = Field(default=None, ge=0)
    investimento_minimo: Decimal | None = Field(default=None, ge=0)
    garantia_fgc: bool = False
    codigo_tesouro: str | None = None
    selic_vigente: Decimal | None = None
    ipca_12m: Decimal | None = None
    source: str
    coletado_em: datetime | None = None
    is_active: bool = True

    @field_validator("nome", "tipo", "source")
    @classmethod
    def _required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field is required")
        return text


class RendaFixaProdutoRead(RendaFixaProdutoIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AssetPriceListResponse(BaseModel):
    items: list[AssetPriceRead]
    total: int
    limit: int
    offset: int


class MacroIndicatorListResponse(BaseModel):
    items: list[MacroIndicatorRead]
    total: int


class RendaFixaListResponse(BaseModel):
    items: list[RendaFixaProdutoRead]
    total: int

class FundamentalQueryResponse(BaseModel):
    total: int
    limit: int
    offset: int


class FiiFundamentalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    name: str
    date: date
    price: Decimal | None = None
    patrimonio_liq: Decimal | None = None
    vpa: Decimal | None = None
    pvp: Decimal | None = None
    dy_12m: Decimal | None = None
    dy_3m_acumulado: Decimal | None = None
    ultimo_rendimento: Decimal | None = None
    data_ultimo_rend: date | None = None
    volume_medio_diario: Decimal | None = None
    liquidez_diaria: Decimal | None = None
    tipo: str | None = None
    segmento: str | None = None
    num_cotistas: int | None = None
    num_imoveis: int | None = None
    vacancia_fisica: Decimal | None = None
    vacancia_financeira: Decimal | None = None
    gestora: str | None = None
    administradora: str | None = None
    taxa_adm: Decimal | None = None
    taxa_performance: Decimal | None = None
    source: str
    coletado_em: datetime


class FiiFundamentalListResponse(FundamentalQueryResponse):
    items: list[FiiFundamentalRead]


class AcaoFundamentalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    name: str
    date: date
    price: Decimal | None = None
    market_cap: Decimal | None = None
    pl: Decimal | None = None
    pvp: Decimal | None = None
    psr: Decimal | None = None
    ev_ebitda: Decimal | None = None
    ev_ebit: Decimal | None = None
    roe: Decimal | None = None
    roa: Decimal | None = None
    roic: Decimal | None = None
    margem_liquida: Decimal | None = None
    margem_ebitda: Decimal | None = None
    cagr_receita_5a: Decimal | None = None
    cagr_lucro_5a: Decimal | None = None
    dy_12m: Decimal | None = None
    payout: Decimal | None = None
    divida_liq_ebitda: Decimal | None = None
    volume_medio_diario: Decimal | None = None
    setor: str | None = None
    subsetor: str | None = None
    source: str
    coletado_em: datetime


class AcaoFundamentalListResponse(FundamentalQueryResponse):
    items: list[AcaoFundamentalRead]


class EtfFundamentalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    name: str
    date: date
    price: Decimal | None = None
    patrimonio_liq: Decimal | None = None
    indice_replicado: str | None = None
    tipo: str | None = None
    taxa_adm: Decimal | None = None
    retorno_12m: Decimal | None = None
    retorno_24m: Decimal | None = None
    tracking_error: Decimal | None = None
    tracking_difference: Decimal | None = None
    volume_medio_diario: Decimal | None = None
    num_cotistas: int | None = None
    gestora: str | None = None
    source: str
    coletado_em: datetime


class EtfFundamentalListResponse(FundamentalQueryResponse):
    items: list[EtfFundamentalRead]


class BdrFundamentalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    name: str
    date: date
    price: Decimal | None = None
    market_cap: Decimal | None = None
    empresa_subjacente: str | None = None
    ticker_original: str | None = None
    bolsa_origem: str | None = None
    pais_origem: str | None = None
    moeda_origem: str | None = None
    cotacao_cambio: Decimal | None = None
    pl: Decimal | None = None
    pvp: Decimal | None = None
    dy_12m: Decimal | None = None
    volume_medio_diario_brl: Decimal | None = None
    nivel_bdr: str | None = None
    source: str
    coletado_em: datetime


class BdrFundamentalListResponse(FundamentalQueryResponse):
    items: list[BdrFundamentalRead]


class CriptoFundamentalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    coin_id: str
    ticker: str
    name: str
    date: date
    price_brl: Decimal | None = None
    price_usd: Decimal | None = None
    market_cap_usd: Decimal | None = None
    market_cap_rank: int | None = None
    volume_24h_usd: Decimal | None = None
    price_change_1h_pct: Decimal | None = None
    price_change_24h_pct: Decimal | None = None
    price_change_7d_pct: Decimal | None = None
    price_change_30d_pct: Decimal | None = None
    price_change_90d_pct: Decimal | None = None
    price_change_1y_pct: Decimal | None = None
    btc_dominance: Decimal | None = None
    circulating_supply: Decimal | None = None
    max_supply: Decimal | None = None
    ath_price_usd: Decimal | None = None
    ath_change_pct: Decimal | None = None
    source: str
    coletado_em: datetime


class CriptoFundamentalListResponse(FundamentalQueryResponse):
    items: list[CriptoFundamentalRead]
