# Fase 20 — ML Baseline Real

## Objetivo

Criar o primeiro baseline real de Machine Learning do Vinance v2 para apoiar o ranking educacional de ativos, usando features quantitativas já calculadas na Fase 18 e retorno futuro como target supervisionado.

Esta fase **não** implementa LSTM, Prophet, deep learning, recomendação definitiva de compra, scraping novo, alteração de providers, frontend ou advisor.

## Módulo criado

`backend/app/intelligence/ml/`

Arquivos:

- `__init__.py`
- `dataset.py`
- `train.py`
- `evaluate.py`
- `model_registry.py`
- `inference.py`
- `schemas.py`
- `router.py`
- `service.py`

## Target definido

O target supervisionado é:

`future_return_{horizon_days}d`

Exemplo para 90 dias:

```text
retorno futuro = preço disponível após D+90 / preço disponível na data da feature - 1
```

Regras aplicadas:

- a feature usada é sempre da data `t`;
- o target usa preço posterior à data da feature;
- registros sem preço inicial ou preço futuro são ignorados;
- o `sample_size` é registrado;
- o treino é bloqueado quando há amostra insuficiente.

## Mercados iniciais

Implementados no baseline inicial:

- ações
- FIIs
- cripto

Ficaram para fase futura:

- ETFs
- BDRs

Motivo: podem exigir histórico/benchmarks mais consistentes antes de um baseline supervisionado confiável.

## Features usadas

As features são lidas das tabelas `*_ml_features` criadas na Fase 18.

### Ações

- `pl_zscore`
- `roe_trend_3m`
- `momentum_30d`
- `momentum_90d`
- `momentum_252d`
- `volatilidade_30d`
- `volatilidade_90d`
- `retorno_vs_ibov`
- `volume_anomaly`
- `score_final`

### FIIs

- `dy_trend_3m`
- `pvp_zscore`
- `vacancia_delta`
- `momentum_30d`
- `momentum_90d`
- `volatilidade_30d`
- `retorno_vs_ifix`
- `score_final`

### Cripto

- `volatilidade_7d`
- `volatilidade_30d`
- `correlacao_btc_30d`
- `momentum_7d`
- `momentum_30d`
- `momentum_90d`
- `volume_anomaly`
- `fear_greed_score`
- `score_final`

## Modelo implementado

Baseline principal:

- `RandomForestRegressor`

Características:

- implementação via scikit-learn;
- `random_state=42`;
- `n_jobs=1` para evitar consumo agressivo em ambiente pequeno;
- `max_depth` e `min_samples_leaf` definidos para reduzir overfitting inicial;
- XGBoost não é obrigatório e não foi usado como dependência exclusiva.

## Avaliação

Métricas implementadas em `evaluate.py`:

- MAE
- RMSE
- Spearman correlation
- hit rate top N
- comparação contra baseline heurístico baseado no `score_final`

O baseline heurístico transforma `score_final` em proxy de retorno apenas para comparação relativa, sem tratar isso como retorno calibrado.

## Model Registry simples

Criado em `model_registry.py`.

Responsabilidades:

- salvar modelo `.joblib`;
- salvar metadata `.metadata.json`;
- versionar por mercado, horizonte e data de treino;
- listar modelos disponíveis;
- carregar modelo mais recente.

Diretório de artefatos:

`data/ml_artifacts/`

O `.gitignore` foi reforçado para não versionar modelos gerados.

## Inference

Criado em `inference.py`.

Funções:

- `predict_asset_scores(market)`
- `rank_assets_with_model(market)`

Regras:

- se não houver modelo, retorna fallback;
- se não houver features recentes, retorna fallback;
- predictions são convertidas em `prediction_score` 0-100 por ranking percentual;
- não há promessa de retorno ou compra.

## Atualização da recommendation engine

`backend/app/intelligence/service.py` foi atualizado para:

1. tentar usar `ml_baseline` quando houver modelo válido;
2. cair para `feature_heuristic_fallback` quando não houver modelo;
3. manter fallback por fundamentos quando não houver features;
4. informar a metodologia usada na resposta.

O fallback heurístico não foi removido.

## Endpoints admin simples

Registrados sob:

`/api/v1/intelligence/ml`

Endpoints:

- `POST /train`
- `GET /status`
- `POST /predict`

Todos exigem autenticação.

## Celery

Criada task:

- `intelligence.train_ml_baselines_weekly`

Decisão operacional:

- a task existe para execução manual ou agendamento futuro;
- o beat **não foi ativado automaticamente** para evitar treinamento semanal sem garantia de histórico suficiente.

## Como evita lookahead bias

A construção do dataset evita lookahead bias básico porque:

- features são selecionadas na data `t`;
- o preço inicial é buscado na data `t` ou próxima data disponível;
- o preço futuro é buscado somente após `t + horizon_days`;
- o target é calculado depois da data da feature;
- o split de treino/teste preserva ordem cronológica.

## Limitações

- Não há calibração avançada de retornos.
- Não há custos, slippage ou imposto no modelo.
- Não há validação walk-forward completa.
- Não há MLflow.
- Não há otimização de hiperparâmetros.
- Não há modelo por regime de mercado.
- ETFs/BDRs ficaram fora do baseline inicial.

## Riscos de overfitting

Riscos principais:

- amostra pequena;
- histórico curto;
- mudanças estruturais do mercado;
- features correlacionadas;
- sobrevivência de ativos no catálogo.

Mitigações iniciais:

- bloqueio por `min_samples`;
- modelo conservador;
- split temporal;
- fallback heurístico mantido;
- comparação com baseline heurístico.

## Por que LSTM/Prophet ficaram fora

LSTM e Prophet foram deixados fora porque esta fase exige:

- target claro;
- baseline simples e auditável;
- menor risco de overfitting;
- menor complexidade operacional;
- sem deep learning prematuro.

## Testes criados

Arquivo:

- `backend/tests/test_fase20_ml_baseline.py`

Coberturas:

- métricas com série válida;
- métricas com série vazia;
- score percentual 0-100;
- fallback heurístico sem modelo;
- ausência de deep learning no módulo ML.

## Validação executada

- `python -m compileall backend/app scripts workers`: OK
- `pytest`: bloqueado no sandbox por dependências ausentes do ambiente, mas testes específicos da Fase 20 foram criados.
- backend startup: não executado no sandbox por ausência de runtime completo do projeto.

## Preparação para Fase 21

A Fase 20 deixa preparado:

- dataset supervisionado por mercado;
- registry local simples;
- inferência com fallback;
- endpoints admin;
- comparação contra baseline heurístico;
- base para walk-forward, validação temporal e melhoria de modelos em fase futura.
