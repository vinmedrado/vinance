# Fase 36 — Histórico de Performance e Validação das Recomendações

## Escopo

A Fase 36 avalia, posteriormente, decisões imutáveis registradas pela Fase 35. Ela não chama o Recommendation Engine, não recalcula ações, scores, guardrails ou perfis e não atualiza `investment_decision_audits`.

Fluxo implementado:

```text
investment_decision_audits (snapshot histórico)
  -> preço de referência
  -> maturidade temporal 1d / 7d / 30d
  -> preço diário do horizonte
  -> retorno e excursões observados
  -> classificação determinística por ação
  -> investment_decision_performance
  -> analytics isolados por usuário e versão
```

## Arquitetura

O módulo `backend/app/investment_performance/` separa:

- `config.py`: horizontes, tolerâncias, faixas e thresholds;
- `models.py`: persistência append-only da avaliação;
- `schemas.py`: contratos de resumo e detalhe;
- `repository.py`: queries de auditoria, preços e inserção idempotente;
- `service.py`: orquestração causal e incremental;
- `evaluator.py`: retorno, excursões, classificação e contexto;
- `metrics.py`: agregações, coortes, calibração e timeline;
- `router.py`: endpoints autenticados somente GET;
- `tasks.py`: tarefa periódica idempotente no Celery existente.

## Fonte de verdade

Somente auditorias com `status=SUCCESS`, ação `BUY`, `WAIT` ou `AVOID`, ativo e mercado válidos são elegíveis. Asset, ação, score, risco, confiança, tendência, perfil e versões vêm diretamente das colunas congeladas pela Fase 35. O estado atual do engine nunca é consultado.

## Política de preços e causalidade

Horizontes são dias corridos a partir de `decision.created_at`:

- `1d`: T0 + 1 dia;
- `7d`: T0 + 7 dias;
- `30d`: T0 + 30 dias.

Preço de referência:

1. usa `investment_decision_audits.price` quando positivo;
2. registra `price_source=decision_snapshot` e `reference_price_timestamp=decision.created_at`;
3. esse timestamp representa a captura do snapshot, pois a Fase 35 não preservava timestamp/provider original da cotação;
4. se o snapshot não contiver preço, usa a barra diária mais próxima estritamente anterior a T0, limitada a 3 dias corridos, pela infraestrutura `asset_prices` já existente.

Preço de avaliação:

1. procura a primeira barra diária cuja data seja o dia-alvo ou um dos 4 dias corridos seguintes;
2. nunca usa simplesmente a barra mais recente;
3. exige que `asset_prices.created_at <= as_of`;
4. uma barra diária só é considerada observável no fim do respectivo dia UTC, política conservadora contra look-ahead;
5. quando a referência veio de `asset_prices`, mantém o mesmo provider; quando veio do snapshot, escolhe provider existente por prioridade determinística;
6. ausência de preço deixa o horizonte pendente para nova execução, sem placeholder persistido.

Mercados da auditoria são normalizados para as convenções existentes de `asset_prices` (`FII/FIIS -> fii`, `ACOES -> acoes`, `ETF -> etf`, `BDR -> bdr`, `CRIPTO -> cripto`).

MFE e MAE usam OHLC diário após T0 até a barra de avaliação, no mesmo provider da avaliação. São movimentos brutos do ativo: MFE é não negativo e MAE é não positivo. A série diária não permite atribuir movimentos intradiários anteriores ou posteriores ao horário exato da decisão; por isso o dia de T0 é excluído das excursões.

## Classificação

A política possui versão própria `decision-performance-v1` e não incrementa versões financeiras da Fase 35.

Thresholds centralizados:

- zona neutra: `-1% < retorno ajustado pela ação < +1%`;
- forte: magnitude a partir de `5%`.

Para `BUY`, retorno ajustado é o retorno observado. Para `WAIT` e `AVOID`, somente a interpretação direcional é invertida: uma queda posterior favorece a coerência de aguardar/evitar e uma alta representa oportunidade perdida. `return_pct` e `absolute_change` permanecem sempre brutos.

Categorias:

- `STRONGLY_CORRECT`: retorno ajustado >= 5%;
- `CORRECT`: retorno ajustado >= 1%;
- `NEUTRAL`: entre -1% e +1%;
- `INCORRECT`: retorno ajustado <= -1% e > -5%;
- `STRONGLY_INCORRECT`: retorno ajustado <= -5%.

O contexto persistido explicita ação, direção observada, magnitude, classificação e que o resultado não representa trade executado.

## Persistência e idempotência

A migration `0016_decision_performance` cria apenas `investment_decision_performance`, vinculada por FK `RESTRICT` a `investment_decision_audits.decision_id`.

Garantias:

- unique constraint em `(decision_id, horizon)`;
- índice `(horizon, evaluated_at)`;
- `INSERT ... ON CONFLICT DO NOTHING` para concorrência segura;
- somente avaliações completas são inseridas;
- reexecuções ignoram horizontes concluídos;
- não há `UPDATE` ou `DELETE` de auditorias ou avaliações.

## Analytics

O resumo calcula, geral e por horizonte:

- decisões históricas;
- observações elegíveis, avaliadas e pendentes maduras;
- retorno posterior médio e mediano;
- percentuais positivo e negativo;
- consistência direcional, excluindo resultados neutros do denominador.

Segmentações disponíveis:

- ação, ativo, risco, tendência e perfil;
- faixas de score (`<60`, `60–<75`, `>=75`);
- faixas de confiança (`<60`, `60–<80`, `>=80`);
- `rule_version`, `recommendation_engine_version`, `score_version` e `guardrail_version`;
- coorte combinada das quatro versões, com `mixed_versions` explícito;
- timeline mensal por horizonte, sempre com elegíveis/avaliadas/pendentes.

Calibração informa confiança média, consistência direcional e gap por faixa. Diagnósticos somente são emitidos a partir de 5 resultados direcionais por faixa; abaixo disso a resposta é `INSUFFICIENT_SAMPLE`. Não existe recalibração de score nesta fase.

## API e segurança

Endpoints sob `/api/v1`, autenticados e com `Cache-Control: private, no-store`:

- `GET /investments/performance`;
- `GET /investments/decisions/{decision_id}/performance`.

Filtros do resumo:

- `asset`, `action`, `horizon`, `risk_level`, `investor_profile`;
- `rule_version`, `recommendation_engine_version`;
- `date_from`, `date_to` com timezone obrigatório.

Ownership é aplicado no join lógico com a auditoria da Fase 35. ID inválido e decisão pertencente a outro usuário retornam o mesmo 404. Anônimo e token inválido retornam 401. Não existem endpoints de escrita.

## Automação

A tarefa `investment_performance.evaluate_due` reutiliza o Celery configurado, a fila `intelligence` e o Beat existente. Executa diariamente às 05:30 no timezone configurado do projeto. A execução é incremental, idempotente e registra somente contagens operacionais, sem snapshots ou dados sensíveis.

## Frontend

`/investir` possui um card discreto e inicialmente recolhido para performance geral. Mostra estados de:

- ausência total de decisões;
- decisões ainda imaturas;
- horizonte maduro sem preço compatível;
- somente 1d disponível;
- histórico parcial 1d/7d/30d;
- erro isolado, sem afetar a decisão atual.

No detalhe de um snapshot histórico, “Ver resultados posteriores” consulta sob demanda os três horizontes. A interface usa “movimento observado”, “consistência” e “resultado posterior”, sem afirmar lucro, causalidade, execução ou garantia.

## Limitações conhecidas

- O banco real validado no início da fase possuía 0 decisões da Fase 35 e, portanto, 0 avaliações maduras. Nenhum dado fictício foi criado.
- `asset_prices` possui granularidade diária; o horário real do fechamento não está armazenado.
- O preço do snapshot da Fase 35 não contém provider/timestamp original, apenas o instante de captura da decisão.
- Retornos são de preço e não incluem dividendos, total return, custos, slippage ou execução.
- Uma avaliação concluída permanece imutável mesmo se um provider corrigir posteriormente uma barra histórica.
