FROM node:24-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json /web/
RUN npm ci
COPY frontend /web/
RUN npm run build

FROM python:3.12-slim AS runtime
ARG INSTALL_RERANK=false
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    LOCAL_EMBEDDING_ENABLED=false \
    CROSS_ENCODER_ENABLED=false \
    UNSTRUCTURED_ENABLED=false
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY app /app/app
COPY eval /app/eval
COPY knowledge /app/knowledge
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY --from=frontend /web/dist /app/frontend/dist
RUN pip install "." \
    && if [ "$INSTALL_RERANK" = "true" ]; then pip install ".[rerank]"; fi \
    && mkdir -p /app/data/local /var/lib/showcase /run/showcase-db \
    && chown -R appuser:appuser /app /var/lib/showcase /run/showcase-db \
    && chmod 0700 /var/lib/showcase && chmod 0755 /run/showcase-db
USER appuser
EXPOSE 8000

# Explicit target used only by compose.showcase.yml; secrets are runtime volumes.
FROM runtime AS showcase
CMD ["python", "-m", "app.demo.docker", "serve"]

# Preserve the pre-existing generic API-image command for other deployments.
FROM runtime AS final
CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
