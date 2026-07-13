from __future__ import annotations

from .config import FEATURE_VERSION
from .market import add_market_context
from .models import FeatureDefinition, FeatureSet
from .momentum import add_cci, add_macd, add_roc, add_rsi, add_stochastic, add_williams_r
from .trend import add_ema, add_hma, add_ichimoku, add_kama, add_sma, add_supertrend, add_wma
from .volatility import add_atr, add_bollinger, add_donchian, add_keltner
from .volume import add_cmf, add_mfi, add_obv, add_vwap


FEATURE_DEFINITIONS: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(
        name="market_context",
        category="market",
        columns=("return_1", "return_3", "return_12", "log_return_1", "range_pct", "close_position_in_range", "volume_zscore_24"),
        function=add_market_context,
        lookback=24,
        description="Returns, candle range and volume normalization.",
    ),
    FeatureDefinition(
        name="sma",
        category="trend",
        columns=("sma_9", "sma_21", "sma_50", "sma_200"),
        function=add_sma,
        lookback=200,
        description="Simple moving averages.",
    ),
    FeatureDefinition(
        name="ema",
        category="trend",
        columns=("ema_9", "ema_21", "ema_50", "ema_200"),
        function=add_ema,
        lookback=200,
        description="Exponential moving averages.",
    ),
    FeatureDefinition(
        name="wma",
        category="trend",
        columns=("wma_9", "wma_21", "wma_50"),
        function=add_wma,
        lookback=50,
        description="Linearly weighted moving averages.",
    ),
    FeatureDefinition(
        name="hma",
        category="trend",
        columns=("hma_21", "hma_55"),
        function=add_hma,
        lookback=62,
        description="Hull moving averages.",
    ),
    FeatureDefinition(
        name="kama",
        category="trend",
        columns=("kama_10_2_30",),
        function=add_kama,
        lookback=30,
        description="Kaufman adaptive moving average.",
    ),
    FeatureDefinition(
        name="supertrend",
        category="trend",
        columns=("supertrend_10_3_0", "supertrend_direction_10_3_0"),
        function=add_supertrend,
        lookback=10,
        description="ATR-based SuperTrend.",
    ),
    FeatureDefinition(
        name="ichimoku",
        category="trend",
        columns=("ichimoku_tenkan_9", "ichimoku_kijun_26", "ichimoku_span_a_current", "ichimoku_span_b_current"),
        function=add_ichimoku,
        lookback=52,
        description="Current-position Ichimoku lines without forward shifting.",
    ),
    FeatureDefinition(
        name="rsi",
        category="momentum",
        columns=("rsi_14",),
        function=add_rsi,
        lookback=14,
        description="Relative strength index.",
    ),
    FeatureDefinition(
        name="macd",
        category="momentum",
        columns=("macd_12_26", "macd_signal_9", "macd_hist_12_26_9"),
        function=add_macd,
        lookback=35,
        description="MACD, signal and histogram.",
    ),
    FeatureDefinition(
        name="roc",
        category="momentum",
        columns=("roc_10", "roc_20"),
        function=add_roc,
        lookback=20,
        description="Rate of change.",
    ),
    FeatureDefinition(
        name="cci",
        category="momentum",
        columns=("cci_20",),
        function=add_cci,
        lookback=20,
        description="Commodity channel index.",
    ),
    FeatureDefinition(
        name="williams_r",
        category="momentum",
        columns=("williams_r_14",),
        function=add_williams_r,
        lookback=14,
        description="Williams percent range.",
    ),
    FeatureDefinition(
        name="stochastic",
        category="momentum",
        columns=("stoch_k_14", "stoch_d_14_3"),
        function=add_stochastic,
        lookback=16,
        description="Stochastic oscillator.",
    ),
    FeatureDefinition(
        name="atr",
        category="volatility",
        columns=("atr_14", "atr_pct_14"),
        function=add_atr,
        lookback=14,
        description="Average true range.",
    ),
    FeatureDefinition(
        name="bollinger",
        category="volatility",
        columns=("bollinger_mid_20_2_0", "bollinger_upper_20_2_0", "bollinger_lower_20_2_0", "bollinger_width_20_2_0", "bollinger_percent_b_20_2_0"),
        function=add_bollinger,
        lookback=20,
        description="Bollinger bands.",
    ),
    FeatureDefinition(
        name="donchian",
        category="volatility",
        columns=("donchian_upper_20", "donchian_lower_20", "donchian_mid_20", "donchian_width_20"),
        function=add_donchian,
        lookback=20,
        description="Donchian channel.",
    ),
    FeatureDefinition(
        name="keltner",
        category="volatility",
        columns=("keltner_mid_20_10_2_0", "keltner_upper_20_10_2_0", "keltner_lower_20_10_2_0", "keltner_width_20_10_2_0"),
        function=add_keltner,
        lookback=20,
        description="Keltner channel.",
    ),
    FeatureDefinition(
        name="vwap",
        category="volume",
        columns=("vwap_20", "vwap_distance_20"),
        function=add_vwap,
        lookback=20,
        description="Rolling volume weighted average price.",
    ),
    FeatureDefinition(
        name="obv",
        category="volume",
        columns=("obv", "obv_change_20"),
        function=add_obv,
        lookback=20,
        description="On-balance volume.",
    ),
    FeatureDefinition(
        name="mfi",
        category="volume",
        columns=("mfi_14",),
        function=add_mfi,
        lookback=14,
        description="Money flow index.",
    ),
    FeatureDefinition(
        name="cmf",
        category="volume",
        columns=("cmf_20",),
        function=add_cmf,
        lookback=20,
        description="Chaikin money flow.",
    ),
)


def get_feature_set() -> FeatureSet:
    return FeatureSet(version=FEATURE_VERSION, definitions=FEATURE_DEFINITIONS)


def feature_columns() -> tuple[str, ...]:
    return get_feature_set().columns


def registry_documentation() -> list[dict[str, object]]:
    return [
        {
            "name": definition.name,
            "category": definition.category,
            "columns": list(definition.columns),
            "lookback": definition.lookback,
            "description": definition.description,
        }
        for definition in FEATURE_DEFINITIONS
    ]
