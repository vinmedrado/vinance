# Vinance Trading Lab

Estrutura inicial para transformar os dados do Vinance em um laboratório quantitativo de criptomoedas.

## Objetivo

Construir um pipeline separado das rotinas financeiras existentes:

```text
coleta OHLCV -> validação -> features -> targets -> modelos -> sinais -> backtest -> paper trading
```

## Segurança operacional

O projeto inicia em `PAPER_ONLY`. O módulo `live_trading` não envia ordens reais enquanto `TRADING_MODE` não for alterado explicitamente e uma implementação de corretora não for adicionada.

## Estrutura

- `market_data/`: clientes de provedores e normalização de dados.
- `candles/`: persistência e validação OHLCV.
- `features/`: indicadores e variáveis de ML.
- `targets/`: criação dos rótulos futuros.
- `models/`: treino, inferência e registro de modelos.
- `signals/`: conversão de previsões em sinais.
- `backtests/`: avaliação cronológica com custos.
- `risk/`: limites, exposição e tamanho de posição.
- `portfolio/`: estado da carteira simulada.
- `execution/`: contratos de execução de ordens.
- `paper_trading/`: execução simulada.
- `live_trading/`: bloqueado por padrão.
- `monitoring/`: métricas e logs.
- `storage/`: acesso ao PostgreSQL e repositórios.
- `scripts/`: comandos operacionais.
- `docs/`: arquitetura e roadmap.

## Primeira execução

1. Copie esta pasta para `vinanceos/backend/trading`.
2. Instale as dependências adicionais listadas em `requirements-trading.txt`.
3. Execute a migração SQL:

```powershell
docker compose exec postgres psql -U vinance -d vinance -f /app/backend/trading/storage/schema.sql
```

Se o container PostgreSQL não enxergar `/app`, copie o SQL ou execute pelo backend usando `psql`.

4. Rode o diagnóstico:

```powershell
docker compose exec backend python -m backend.trading.scripts.check_setup
```

5. Inicie pela coleta de candles. A base atual de `cripto_fundamentals` pode ser usada como fonte complementar, mas não substitui OHLCV.

## Variáveis de ambiente

```env
TRADING_MODE=PAPER_ONLY
TRADING_EXCHANGE=binance
TRADING_SYMBOLS=BTCUSDT,ETHUSDT
TRADING_INTERVAL=5m
TRADING_LOOKBACK_DAYS=365
TRADING_FEE_BPS=10
TRADING_SLIPPAGE_BPS=5
TRADING_MAX_POSITION_PCT=0.05
TRADING_MAX_DAILY_LOSS_PCT=0.02
```

## Ordem recomendada

1. Coleta histórica de candles.
2. Validação de lacunas e duplicidades.
3. Geração de features.
4. Criação de targets.
5. Baseline com regressão logística e LightGBM/XGBoost.
6. Backtest walk-forward.
7. Paper trading por algumas semanas.
8. Avaliação antes de qualquer integração real.
