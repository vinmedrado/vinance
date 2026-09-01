# Onda E — aposentadoria definitiva do tooling SQLite legado

## Resultado

A Onda E remove os últimos consumidores executáveis de `pg_compat`, os entry
points que dependiam das stacks aposentadas nas ondas anteriores e as cadeias
antigas de ML, automação, background jobs, agents e workers.

Nenhuma compatibilidade SQLite foi recriada. O importador de planilha pessoal e
o migrador SQLite genérico também foram aposentados: ambos possuíam destino
implícito, ausência de ownership inequívoco ou comportamento destrutivo. Os
arquivos locais `financas.xlsm` e `b3.xlsx` não foram abertos, movidos ou
alterados.

## Runtime canônico

- FastAPI: `backend.app.main`;
- API: `backend.app.api.v1.router`;
- Celery/Beat: `backend.app.core.celery.celery_app`;
- persistência: PostgreSQL assíncrono e migrations Alembic;
- inteligência: Recommendation Engine e Fases 35–37;
- pesquisa e trading: `backend/trading` V2.

`docker-compose.yml` já utilizava o Celery canônico. O `render.yaml` foi
atualizado antes da remoção do wrapper `workers.celery_app`.

## Tooling preservado

O `scripts/production_readiness_check.py` permanece como diagnóstico explícito.
Seu import não abre conexão, não cria schema e não executa verificações. Quando
invocado pelo operador, ele usa o health service e o Celery oficiais e apenas
inspeciona os fontes de produto em busca de compatibilidade SQLite residual.

Não permanece tooling SQLite executável. Referências textuais restantes estão
restritas a testes de ausência, documentação histórica e migrations Alembic.

## Garantias

- callers de `pg_compat`: zero;
- arquivo executável `pg_compat.py`: removido;
- runtime moderno SQLite: zero;
- DDL manual no runtime moderno: zero;
- schema alterado: não;
- migration criada: não;
- dados alterados: não;
- artifacts e outputs Trading V2 removidos: não.
