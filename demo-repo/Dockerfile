# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.8.17 AS uv

FROM python:3.11-slim

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app
COPY demo-repo/pyproject.toml demo-repo/uv.lock ./
COPY demo-repo/app ./app
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 9000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]

