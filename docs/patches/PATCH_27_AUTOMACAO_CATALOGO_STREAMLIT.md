# PATCH 27 — Automação do Catálogo pela Interface Streamlit

## Entregue

- Nova página `pages/10_Automacao_Catalogo.py`.
- Upload seguro de Excel `.xlsx` para importação seed do `asset_catalog`.
- Botões Streamlit para:
  - importar Excel seed;
  - sincronizar criptos;
  - validar catálogo;
  - atualizar scores de qualidade;
  - sincronizar `asset_catalog` → `assets`;
  - rodar pipeline completo.
- Registro de execuções na tabela `catalog_pipeline_runs`.
- Histórico visível na própria página.
- Atualização da página de saúde para exibir últimas execuções e erros recentes.
- Execução por subprocess seguro usando somente scripts conhecidos do projeto.
- Scripts existentes continuam funcionando via terminal.

## Segurança

- Upload limitado a `.xlsx`.
- Não executa comandos arbitrários.
- Arquivo temporário de upload é removido ao final.
- Não apaga banco, catálogo ou tabelas.
- Operações usam scripts já existentes.
