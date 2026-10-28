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
- storage: migrations externas versionadas, backup/restore e repositórios compartilhados.
- model_registry: promoção auditável de pesquisa para Paper, bloqueada por Validation V2.
- paper_orchestration: execução manual `run-once` de predição para sinal Paper; sem scheduler.
- app/trading: API autenticada, owner-only, risk budget e persistência do produto.
- scripts/experiment_campaign_v2.py: campanha oficial V2.

## Propriedade do schema

As tabelas operacionais de Trading V2 são mantidas pelo lifecycle externo em
`storage/migrate.py`. `storage/schema.sql` é apenas a referência histórica da
revisão inicial e não deve ser aplicado para provisionar ambientes novos. O
domínio continua intencionalmente excluído de `Base.metadata` e do autogenerate
do Alembic principal.

## Diagnóstico seguro

Use python -m backend.trading.scripts.check_setup para verificar configuração e
conectividade. Testes automatizados não executam campanhas de treino nem backtests
persistentes.

Use `python -m backend.trading.storage.migrate check` para validar o schema e
`python -m backend.trading.model_registry.cli check` para consultar readiness.
Nenhuma task Trading é registrada no Celery Beat.
