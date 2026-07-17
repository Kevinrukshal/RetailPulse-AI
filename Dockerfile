FROM python:3.14-slim

ARG INSTALL_DEV=false
ARG INSTALL_AI=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system retailpulse \
    && adduser --system --ingroup retailpulse --home /app retailpulse

COPY pyproject.toml README.md LICENSE alembic.ini ./
RUN mkdir -p app etl \
    && touch app/__init__.py etl/__init__.py \
    && if [ "$INSTALL_DEV" = "true" ] && [ "$INSTALL_AI" = "true" ]; then \
        python -m pip install --no-cache-dir ".[dev,ai]"; \
    elif [ "$INSTALL_DEV" = "true" ]; then \
        python -m pip install --no-cache-dir ".[dev]"; \
    elif [ "$INSTALL_AI" = "true" ]; then \
        python -m pip install --no-cache-dir ".[ai]"; \
    else \
        python -m pip install --no-cache-dir .; \
    fi

COPY app ./app
COPY ai ./ai
COPY etl ./etl
COPY migrations ./migrations
COPY sql ./sql
COPY scripts ./scripts
COPY tests ./tests
COPY docs ./docs
COPY dashboard ./dashboard

RUN mkdir -p /app/data/processed /app/data/rejected /app/data/sample \
    && chown -R retailpulse:retailpulse /app

USER retailpulse

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
