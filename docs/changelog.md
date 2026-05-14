# Changelog

## Refatoração estrutural para GitHub/portfólio

- Criada estrutura documental em `docs/`.
- Histórico de patches movido para `docs/patches/`.
- Entrada Streamlit movida de `app.py` para `legacy_streamlit/main_streamlit.py` para permitir criação do pacote `app/`.
- Docker Compose atualizado para apontar para a nova entrada do Streamlit.
- `.gitignore` revisado para Python, dados locais e artefatos temporários.
- `requirements.txt` deduplicado sem atualização forçada de versões.
