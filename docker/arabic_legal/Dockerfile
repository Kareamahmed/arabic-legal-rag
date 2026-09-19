FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first (cached unless pyproject.toml or uv.lock change)
COPY src/pyproject.toml src/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application code
COPY src/ .

RUN mkdir -p /app/models/db_schemes/arabic_legal/

COPY docker/arabic_legal/alembic.ini /app/models/db_schemes/arabic_legal/alembic.ini

COPY docker/arabic_legal/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]