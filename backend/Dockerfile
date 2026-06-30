FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev

COPY backend/src ./backend/src
COPY backend/migrations ./backend/migrations
COPY backend/alembic.ini ./backend/alembic.ini

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "digitalcard.main:app", "--app-dir", "backend/src", "--host", "0.0.0.0", "--port", "8000"]
