
FROM python:3.11-slim

ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/vinance

RUN groupadd --gid ${APP_GID} vinance \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /usr/sbin/nologin vinance

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

ARG APP_VERSION=2.0.0
ARG APP_COMMIT_SHA=unknown

ENV APP_VERSION=${APP_VERSION} \
    APP_COMMIT_SHA=${APP_COMMIT_SHA}

LABEL org.opencontainers.image.title="VinanceOS backend" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${APP_COMMIT_SHA}"

COPY --chown=vinance:vinance . .
RUN chown vinance:vinance /app \
    && mkdir -p \
        /app/logs \
        /app/run \
        /app/data/ml_artifacts \
        /app/backend/trading/artifacts/ml_engine_v2 \
        /app/backend/trading/output \
    && chown -R vinance:vinance \
        /app/logs \
        /app/run \
        /app/data/ml_artifacts \
        /app/backend/trading/artifacts \
        /app/backend/trading/output

USER vinance

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
