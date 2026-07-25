# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.8.17 AS uv

FROM python:3.11-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src
COPY specs /specs
COPY demo-repo /demo-repo
RUN uv sync --frozen --no-dev \
    && uv pip install pytest \
    && git -C /demo-repo init -b main \
    && git -C /demo-repo config user.email "demo@mergegate.local" \
    && git -C /demo-repo config user.name "MergeGate Demo" \
    && git -C /demo-repo add . \
    && git -C /demo-repo commit -m "Baseline demo repository"

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn mergegate.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
