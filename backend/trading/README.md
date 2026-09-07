# Vinance Trading V2

Trading V2 é a única stack operacional de trading do repositório. A antiga stack V1 e
seus entrypoints foram aposentados; o histórico persistido e os artefatos V2 foram
preservados.

## Fluxo canônico

market_data -> history_expansion_v2 -> feature_store -> target_engine ->
ml_engine -> prediction_engine -> backtesting_v2 -> research_v2 ->
validation_v2 -> paper_trading_v2

## Segurança operacional

O runtime permanece PAPER_ONLY. Não existe entrypoint de live trading nem integração
para envio de ordens reais.

## Componentes

- market_data: clientes públicos e normalização.
- history_expansion_v2: expansão histórica e integridade OHLCV.
- feature_store: Feature Store V2 incremental.
- target_engine: Target Engine V2.
- ml_engine: treino e registro de modelos V2.
- prediction_engine: inferência e decisões V2.
- backtesting_v2: simulação cronológica e walk-forward.
- research_v2 e validation_v2: pesquisa, robustez e validação.
- paper_trading_v2: execução exclusivamente simulada.
- storage: schema SQL explícito e repositórios compartilhados.
- scripts/experiment_campaign_v2.py: campanha oficial V2.

## Propriedade do schema

As seis tabelas operacionais de Trading V2 são mantidas pelo SQL explícito em
storage/schema.sql. Elas são um domínio externo intencional ao Base.metadata do
backend e são excluídas da comparação de autogenerate do Alembic principal.

## Diagnóstico seguro

Use python -m backend.trading.scripts.check_setup para verificar configuração e
conectividade. Testes automatizados não executam campanhas de treino nem backtests
persistentes.
