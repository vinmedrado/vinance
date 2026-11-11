# Vinance — Technical case study

*English / Español · Financial data, backend architecture and analytical workflows*

## The problem

Personal financial analysis becomes fragmented when budgets, transactions, investments and projections are managed in separate tools and files. A useful system must connect these domains while keeping data access and business rules manageable.

## System design

\`\`\`text
React / Vite interface
        ↓
FastAPI services (finance, ERP, market, analysis)
        ↓
PostgreSQL + data services and domain logic
        ↘ optional Redis / Celery background workflows
\`\`\`

The official user interface lives in \`frontend/\`; the historical Streamlit UI remains in \`legacy_streamlit/\` for older administrative workflows. Business logic is distributed across \`backend/app/\`, \`services/\` and analytical modules.

## What this demonstrates

- Domain-oriented API development with Python/FastAPI.
- Analytical pipelines, financial indicators and investment analysis.
- Separation between UI, persistence, operations and background processing.
- Incremental modernization while keeping legacy operational paths accessible.

## Quality evidence

The [CI workflow](../.github/workflows/ci.yml) runs Python compilation and \`pytest\`, a React/Vite frontend build and Docker Compose syntax validation for development and production Compose files. CI uses example environment values instead of production secrets.

## Trade-offs and limitations

Financial insights require appropriate data quality, market context and human review. This is a **software engineering portfolio project**, not a certified investment adviser or a claim of audited production operations. Testing and Compose validation do not prove a live deployment is secure.

## Explore

- [Repository](https://github.com/vinmedrado/vinance)
- [Architecture](architecture.md)
- [Security](SECURITY.md)
- [CI](https://github.com/vinmedrado/vinance/actions/workflows/ci.yml)

---

## Resumen en español

**Problema:** la información financiera personal está fragmentada entre presupuestos, transacciones e inversiones.

**Solución:** aplicación modular con React, FastAPI, PostgreSQL y servicios de datos para unificar información, generar indicadores y apoyar el análisis financiero. Puede utilizar procesos asíncronos con Redis/Celery.

**Competencias demostradas:** Python, arquitectura de APIs, integración de datos, procesos asíncronos, pruebas y modernización de sistemas existentes.

**Limitación explícita:** el proyecto demuestra ingeniería de software; no representa asesoramiento financiero certificado ni una implantación de producción auditada.

[Ver código](https://github.com/vinmedrado/vinance)
