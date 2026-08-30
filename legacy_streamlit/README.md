# Interface Streamlit aposentada

A interface Streamlit histórica foi retirada na Onda A da limpeza do legado
SQLite. Ela não fazia parte do runtime FastAPI, do Celery nem dos arquivos
Compose atuais, e dependia de contratos SQLite incompatíveis com a arquitetura
oficial.

O frontend suportado do VinanceOS é o React/Vite em `frontend/`. O histórico da
interface removida permanece recuperável pelo Git; este diretório não contém
mais um ponto de entrada executável.
