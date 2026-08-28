# FASE 17B-1 — Diagnostic Script Status Invest

Projeto: Vinance v2  
Base: `vinance_v2_fase16_providers_reais(1).zip` + `PRE_FASE_17_STATUSINVEST_RESEARCH.md` + `FASE_17A_STATUSINVEST_XHR_CONFIRMATION.md`  
Tipo: diagnóstico técnico isolado, sem integração operacional

---

## 1. Objetivo da fase

Esta fase criou scripts controlados para confirmar, em execução local, o comportamento atual do endpoint público candidato do Status Invest antes da implementação do provider definitivo.

O foco é confirmar:

- payloads reais;
- `CategoryType` real;
- nomes reais dos campos retornados;
- headers mínimos;
- formato JSON real;
- comportamento de erro, bloqueio, rate limit ou endpoint ausente.

A fase **não criou provider final**, **não criou scraping operacional**, **não criou tasks Celery**, **não persistiu dados**, **não alterou backend/app**, **não alterou frontend**, **não criou migrations** e **não integrou nada ao backend operacional**.

---

## 2. Arquivos criados

Pasta criada:

```text
scripts/statusinvest_diagnostics/
```

Arquivos criados:

```text
scripts/statusinvest_diagnostics/common.py
scripts/statusinvest_diagnostics/test_acoes_search.py
scripts/statusinvest_diagnostics/test_fiis_search.py
scripts/statusinvest_diagnostics/README.md
FASE_17B1_STATUSINVEST_DIAGNOSTICS.md
```

---

## 3. Arquivos operacionais não alterados

Foram preservados sem alteração operacional:

```text
backend/app/
frontend/src/
backend/app/core/celery.py
backend/alembic/
backend/app/market/providers/
backend/app/market/scheduler/tasks.py
backend/app/advisor/
```

Não houve criação de:

- provider definitivo Status Invest;
- parser final;
- integração com banco;
- scheduler;
- Celery task;
- migration;
- endpoint;
- frontend;
- ML.

---

## 4. Endpoint diagnosticado

Endpoint candidato primário, conforme Pré-Fase 17 e Fase 17A:

```text
GET https://statusinvest.com.br/category/advancedsearchresult
```

Parâmetros diagnosticados:

```text
search=<JSON URL-encoded>
CategoryType=<number>
```

Referers usados:

```text
https://statusinvest.com.br/acoes/busca-avancada
https://statusinvest.com.br/fundos-imobiliarios/busca-avancada
```

---

## 5. Headers mínimos usados

Os scripts usam headers conservadores:

```http
User-Agent: browser comum
Accept: application/json, text/plain, */*
Accept-Language: pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7
Referer: página pública correta do mercado
Origin: https://statusinvest.com.br
Connection: keep-alive
```

Não foi usado:

- cookie fixo;
- proxy;
- bypass;
- CAPTCHA solver;
- Playwright;
- Selenium;
- browser automation;
- estratégia agressiva anti-bot.

---

## 6. Script de ações

Arquivo:

```text
scripts/statusinvest_diagnostics/test_acoes_search.py
```

Objetivo:

- testar `advancedsearchresult` para ações;
- confirmar `CategoryType=1`;
- imprimir payload enviado;
- imprimir URL final;
- imprimir status code;
- imprimir tempo de resposta;
- imprimir content-type;
- imprimir tamanho da resposta;
- resumir os primeiros campos do JSON;
- salvar raw opcionalmente em `temp/statusinvest/` com `--save-raw`.

### 6.1 CategoryType usado para ações

```text
CategoryType=1
```

Status:

```text
confirmado por referência pública e mantido como candidato principal para validação local
```

### 6.2 Payload diagnóstico de ações

O payload contém filtros sem restrição para mapear campos reais, incluindo:

```text
Sector
SubSector
Segment
my_range
dy
p_L
peg_Ratio
p_VP
p_Ativo
margemBruta
margemEbit
margemLiquida
p_Ebit
eV_Ebit
dividaLiquidaEbit
dividaLiquidaPatrimonioLiquido
p_SR
p_CapitalGiro
p_AtivoCirculanteLiquido
roe
roic
roa
liquidezCorrente
patrimonioAtivo
passivoAtivo
giroAtivos
cagrReceitas5Anos
cagrLucros5Anos
liquidezMediaDiaria
vpa
lpa
valorMercado
```

Campos-alvo da futura normalização:

```text
ticker
name
price
pl
pvp
psr
roe
roic
margem_liquida
margem_ebit
dy_12m
divida_liq_ebit
liquidez_media_diaria
setor/subsetor/segmento
```

---

## 7. Script de FIIs

Arquivo:

```text
scripts/statusinvest_diagnostics/test_fiis_search.py
```

Objetivo:

- investigar/confirmar `CategoryType` de FIIs;
- testar candidatos leves;
- imprimir payload enviado;
- imprimir campos encontrados no JSON;
- verificar por substring se a resposta contém campos relacionados a:
  - `pvp`;
  - `dy`;
  - `liquidez`;
  - `segmento`;
  - `patrimonio`;
  - `vpa`.

### 7.1 CategoryTypes candidatos para FIIs

Por padrão, o script testa:

```text
CategoryType=2
CategoryType=3
CategoryType=4
```

Também permite forçar um candidato:

```bash
python scripts/statusinvest_diagnostics/test_fiis_search.py --category-type 2
```

Status:

```text
FIIs ainda exigem confirmação local live; a Fase 17A classificou CategoryType=2 como provável, mas não definitivamente confirmado.
```

### 7.2 Payload diagnóstico de FIIs

O payload diagnóstico inclui:

```text
Segment
my_range
dy
p_VP
valorPatrimonial
liquidezMediaDiaria
vpa
patrimonioLiquido
```

Campos-alvo da futura normalização:

```text
ticker
name
price
pvp
dy_12m
liquidez_diaria
segmento
patrimonio_liq
vpa
```

Campos que provavelmente ainda podem exigir fallback de detalhe/HTML se não vierem no JSON da busca:

```text
vacancia_fisica
vacancia_financeira
gestora
taxa_adm
num_cotistas
num_imoveis
tipo
```

---

## 8. Logging implementado

Os scripts mostram:

- URL final;
- params enviados;
- status code;
- tempo de resposta em ms;
- content-type;
- tamanho da resposta;
- resumo dos primeiros campos do JSON;
- amostra compacta do JSON;
- erros 403/429/404 com mensagem clara;
- falhas de rede/timeout sem stack trace desnecessário.

---

## 9. Salvamento raw opcional

Por padrão, os scripts **não salvam respostas**.

O salvamento raw só acontece se o operador passar:

```bash
--save-raw
```

Destino:

```text
temp/statusinvest/
```

Uso recomendado:

- somente durante diagnóstico manual;
- não versionar arquivos raw;
- apagar respostas após análise se contiverem dados volumosos.

---

## 10. Segurança operacional

Medidas implementadas:

- timeout HTTP;
- retry leve;
- sleep entre retries/chamadas;
- headers conservadores;
- sem cookies fixos;
- sem proxy;
- sem bypass;
- sem concorrência;
- sem persistência;
- sem banco;
- sem Celery;
- sem parser definitivo.

Os scripts retornam sucesso de processo quando a execução controlada termina, mesmo se o endpoint responder com erro HTTP ou se a rede local falhar. Isso é intencional para diagnóstico: o erro é parte do resultado investigativo e é exibido no log.

---

## 11. Validação executada

Comandos executados no ambiente sandbox:

```bash
python scripts/statusinvest_diagnostics/test_acoes_search.py --timeout 1 --retries 0
python scripts/statusinvest_diagnostics/test_fiis_search.py --timeout 1 --retries 0 --sleep 0
```

Resultado:

```text
scripts executaram corretamente
logs foram emitidos
não houve persistência
não houve banco
não houve integração operacional
```

Limitação do sandbox:

```text
As chamadas externas diretas via Python falharam com DNS: Temporary failure in name resolution.
```

Impacto:

```text
A execução estrutural dos scripts foi validada, mas a confirmação live dos payloads reais deve ser feita em ambiente local com acesso à internet e DNS funcional.
```

---

## 12. Endpoints aprovados para diagnóstico

```text
GET https://statusinvest.com.br/category/advancedsearchresult
```

Com referers:

```text
https://statusinvest.com.br/acoes/busca-avancada
https://statusinvest.com.br/fundos-imobiliarios/busca-avancada
```

---

## 13. Endpoints rejeitados nesta fase

Não foram promovidos para diagnóstico operacional:

```text
/category/tickerprice
páginas individuais HTML de ativos
qualquer endpoint não confirmado para busca avançada
```

Motivo:

- `tickerprice` apareceu como referência histórica, mas não deve ser fonte primária sem nova confirmação;
- páginas individuais podem exigir HTML parsing e selectors, o que deve ser fallback e não estratégia principal.

---

## 14. Recomendações para o provider final da Fase 17

1. Começar pelo endpoint `advancedsearchresult`.
2. Confirmar localmente `CategoryType=1` para ações.
3. Confirmar localmente o `CategoryType` real de FIIs, começando por `2`.
4. Mapear nomes reais de campos a partir dos logs dos scripts.
5. Criar normalizador só depois de salvar/analisar amostras raw.
6. Usar fallback HTML apenas para campos ausentes e com baixa frequência.
7. Evitar Playwright na operação normal.
8. Usar Playwright apenas como ferramenta manual de investigação se XHR não for suficiente.
9. Não usar cookies fixos, bypass ou scraping agressivo.
10. Implementar provider final com batch pequeno, retry, rate limit e persistência incremental somente na Fase 17 operacional.

---

## 15. Abordagem recomendada

```text
httpx + XHR JSON + payload controlado + batch pequeno + retry leve + rate limit conservador
```

Somente se necessário:

```text
BeautifulSoup/lxml para páginas individuais específicas, como fallback de campos que não aparecem no JSON
```

Playwright:

```text
Apenas fallback de pesquisa/manual, não runtime operacional padrão
```

---

## 16. Abordagem não recomendada

Não recomendado:

- raspar tabelas grandes por selectors HTML como fonte primária;
- usar Playwright para cada ativo;
- usar concorrência alta;
- usar cookies fixos;
- tentar contornar proteção anti-bot;
- persistir payload cru no banco;
- criar provider antes de confirmar os nomes reais do JSON.

---

## 17. Plano para futura Fase 17

Após executar estes scripts em ambiente local com internet:

1. Salvar raw de ações e FIIs com `--save-raw`.
2. Confirmar `CategoryType` de FIIs.
3. Criar tabela de mapeamento campo Status Invest → campo Vinance.
4. Implementar provider final em `backend/app/market/providers/statusinvest.py`.
5. Implementar service de normalização/persistência.
6. Implementar tasks Celery apenas depois do provider testado.
7. Adicionar testes sem chamadas reais.
8. Documentar limites operacionais e campos que dependem de fallback.

---

## 18. Status final da Fase 17B-1

```text
Scripts diagnósticos isolados criados: SIM
Provider final criado: NÃO
Scraping operacional criado: NÃO
Celery alterado: NÃO
Banco usado: NÃO
Frontend alterado: NÃO
Migrations criadas: NÃO
ML criado: NÃO
Logs úteis implementados: SIM
Salvamento raw opcional: SIM
Confirmação live no sandbox: BLOQUEADA POR DNS DO AMBIENTE
Pronto para execução local controlada: SIM
```
