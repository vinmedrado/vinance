from .score_top_n import ScoreTopNStrategy
from .momentum import MomentumStrategy
from .dividend_yield import DividendYieldStrategy
from .low_volatility import LowVolatilityStrategy
from .multi_factor import MultiFactorStrategy

STRATEGIES = {
    'score_top_n': ScoreTopNStrategy,
    'momentum': MomentumStrategy,
    'dividend_yield': DividendYieldStrategy,
    'low_volatility': LowVolatilityStrategy,
    'multi_factor': MultiFactorStrategy,
}


def get_strategy(name: str):
    try:
        return STRATEGIES[name]
    except KeyError as exc:
        valid = ', '.join(sorted(STRATEGIES))
        raise ValueError(f'Estratégia inválida: {name}. Válidas: {valid}') from exc
