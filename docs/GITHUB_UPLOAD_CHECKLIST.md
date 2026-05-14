# Checklist de Upload para GitHub — FinanceOS

Este checklist deve ser usado antes de publicar o FinanceOS em repositório público ou portfólio.

## Arquivos que NÃO devem ir ao GitHub

Confirme que estes itens não estão versionados:

- `.env`
- `.env.local`
- `.env.production`
- `.env.development`
- qualquer arquivo real de credenciais
- `_archive_review/secrets/`
- `_archive_review/local_data/`
- `data/financas.db`
- bancos SQLite locais reais (`*.db`, `*.sqlite`, `*.sqlite3`)
- `__pycache__/`
- `*.pyc`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `logs/`
- `*.log`
- `dist/`
- `build/`
- arquivos temporários (`*.tmp`, `*.temp`, `*~`)

## Comandos de validação

```bash
python -m compileall .
python -c "import importlib; [importlib.import_module(m) for m in ['backend.app.main','db.database','services.final_ranking_service']]"
docker compose config
```

## Como rodar localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
streamlit run legacy_streamlit/app.py
```

Para Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run legacy_streamlit/app.py
```

## Como rodar com Docker

```bash
docker compose up --build
```

Para validar a configuração antes de subir:

```bash
docker compose config
```

## Checklist antes do push

- [ ] Rodei `python -m compileall .` sem erro.
- [ ] Rodei `docker compose config` sem erro.
- [ ] Rodei o Streamlit com `streamlit run legacy_streamlit/app.py`.
- [ ] Criei `.env` local a partir de `.env.example`.
- [ ] Confirmei que nenhum `.env` real será enviado.
- [ ] Confirmei que `data/financas.db` não está no projeto versionável.
- [ ] Confirmei que `_archive_review/` não será enviado ao GitHub público.
- [ ] Confirmei que `docs/patches/` contém o histórico de patches.
- [ ] Revisei `README.md`, `docs/architecture.md`, `docs/roadmap.md` e `docs/refactor_report.md`.

## Observação importante

O FinanceOS é uma ferramenta de análise, estudo, backtesting e apoio à decisão. Ele não representa recomendação financeira, consultoria de investimento ou garantia de retorno.
