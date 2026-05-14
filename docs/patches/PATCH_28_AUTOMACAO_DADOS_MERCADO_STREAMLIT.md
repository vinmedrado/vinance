# PATCH 28 — Automação de Dados de Mercado pela Interface Streamlit

## Objetivo
Eliminar a dependência do terminal para atualização manual de dados de mercado no FinanceOS.

## Entregas

- Nova página `pages/11_Automacao_Dados_Mercado.py`.
- Execução via interface Streamlit para:
  - Histórico de preços.
  - Dividendos.
  - Índices / benchmarks.
  - Indicadores macro / CDI.
  - Pipeline completo de dados.
- Execução segura por `subprocess.run` com:
  - `shell=False`.
  - Lista explícita de argumentos.
  - `sys.executable`.
  - `cwd` fixado na raiz do projeto.
  - `PYTHONPATH` controlado.
  - Timeout configurado.
- Criação automática da tabela `market_data_pipeline_runs`.
- Registro de histórico de execuções com parâmetros, resumo, stdout/stderr e erro amigável.
- Integração com `pages/8_Saude_do_Sistema.py`.
- Atalho em `pages/2_Cobertura_de_Dados.py` para a nova página.

## Arquivos alterados/criados

- Criado: `pages/11_Automacao_Dados_Mercado.py`
- Criado: `services/market_data_pipeline_runs.py`
- Alterado: `pages/8_Saude_do_Sistema.py`
- Alterado: `pages/2_Cobertura_de_Dados.py`
- Criado: `PATCH_28_AUTOMACAO_DADOS_MERCADO_STREAMLIT.md`

## Arquivos preservados

Não foram alterados:

- `multi_factor.py`
- `strategy_runner.py`
- lógica de estratégia
- scripts de sincronização existentes, que continuam funcionando pelo terminal

## Execução

```bash
streamlit run legacy_streamlit/app.py
```

Depois, abrir a página:

```text
Automação de Dados de Mercado
```

## Observação

Este patch não implementa execução em background, scheduler, fila de jobs, automação diária ou agentes de IA. Esses pontos ficam para patch posterior.
