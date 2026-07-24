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
# The demo acceptance contract executes pytest inside the backend process.
# Keep the locked dev group in the image so the Compose demo can produce a
# real red/green verdict instead of failing because its test runner is absent.
RUN uv sync --frozen

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "mergegate.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
