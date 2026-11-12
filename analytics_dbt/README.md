# Vinance | dbt Analytics (isolated, opt-in)

Modulo **opcional** para demonstrar SQL, modelagem, testes e marts analiticos com dbt Core + PostgreSQL. Nao altera backend, frontend, migrations, Airflow, Celery ou tabelas operacionais existentes.

## Arquitetura

```text
Vinance pipelines -> public.asset_prices (read-only)
                         |
                         v
             stg_asset_prices (view)
                         |
                         v
          mart_daily_asset_prices (view)
                         |
                         v
         mart_latest_asset_prices (view)
```

Os modelos dbt sao criados em esquemas proprios (`vinance_analytics_staging` e `vinance_analytics_marts`), separados de `public`. Nao ha hooks de escrita no esquema operacional.

## Setup local (sem Snowflake)

1. Na raiz do Vinance, suba apenas o banco local: `docker compose up -d postgres`.
2. Entre em `analytics_dbt/`, crie um ambiente virtual Python independente e instale `pip install -r requirements.txt`.
3. Copie `profiles.yml.example` para `profiles.yml` (ignorado pelo Git).
4. Configure a variavel `VINANCE_DBT_PASSWORD` com a senha do **seu PostgreSQL local**.
5. Execute:
   ```bash
   dbt debug --profiles-dir .
   dbt build --profiles-dir .
   ```

O `docker-compose.yml` atual publica o Postgres local na porta **5434**. As tabelas de origem (`public.asset_prices`) precisam existir no banco local (migrations da aplicacao). O modulo pode criar as views mesmo sem precos, mas necessita da tabela de origem.

No PowerShell: `$env:VINANCE_DBT_PASSWORD = "sua-senha-local"`.

**Seguranca:** nao use base, conta, credenciais ou dados da Stellantis. Nao conecte este projeto ao ambiente de producao sem revisar permissoes e custo. Idealmente conceda ao usuario dbt apenas `SELECT` nas fontes e `CREATE/USAGE` nos esquemas analiticos, sem permissao de alterar tabelas operacionais.

## Qualidade e limites

- `dbt build` executa as views e testes de unicidade / nulidade documentados.
- Valores `close <= 0` nao entram nos marts, mas permanecem na origem e staging para auditoria.
- A visao diaria seleciona a observacao mais recente de cada dia por simbolo e fonte (adequada para varias coletas de cripto).
- **Nao executa automaticamente no app** e nao adiciona dependencias ao `requirements.txt` principal.
- **Nao substitui o agendador existente**. Orquestracao com Airflow fica para uma fase posterior, depois de validar a branch e decidir como integrar com a versao local em desenvolvimento.
- Este modulo e um primeiro passo de aprendizado/portfolio, nao uma migracao de todo o Vinance para dbt.

## Integracao segura com sua versao local

O desenvolvimento fica em uma branch separada. Quando voce terminar seu trabalho local:

```bash
git status
git add -A
git commit -m "Minha versao atualizada do Vinance"
git push origin main
git fetch origin
git checkout main
git pull --ff-only
git merge --no-ff feat/dbt-analytics-isolated
```

**Nao execute os comandos acima cegamente**: ajuste ao nome real da sua branch local, revise o diff/PR e confirme que nao ha alteracoes sem commit. Nao use `push --force`; se houver conflito, resolva-o antes de integrar. A branch de dbt nao modifica `main` ate que o merge seja realizado.
