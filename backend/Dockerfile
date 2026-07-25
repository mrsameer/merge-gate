# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.8.17 AS uv

FROM python:3.11-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y git \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 mergegate \
    && useradd --uid 10001 --gid mergegate --create-home --shell /usr/sbin/nologin mergegate

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
    && git -C /demo-repo commit -m "Baseline demo repository" \
    && mkdir -p /data \
    && chown -R mergegate:mergegate /app /data /demo-repo

ENV PATH="/app/.venv/bin:${PATH}" \
    MERGEGATE_DATA_DIR="/data" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "chown -R mergegate:mergegate /data && export HOME=/home/mergegate USER=mergegate LOGNAME=mergegate && exec runuser -u mergegate --preserve-environment -- sh -c 'uvicorn mergegate.api.main:app --host 0.0.0.0 --port ${PORT:-8000}'"]
