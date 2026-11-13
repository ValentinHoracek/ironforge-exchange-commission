# IFEC ingest job image. Public on GHCR: it must never contain secrets.
# Credentials arrive at runtime as environment variables (Container Apps -> Key Vault).
# Base images are pinned by digest: a tag can be re-pointed, a digest cannot.

# --- Build stage: install exactly the locked dependencies ---------------------------------
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# --- Runtime stage: Python + the finished environment, no build tools ---------------------
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

RUN useradd --system --uid 10001 --no-create-home ifec
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY config ./config

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1

USER 10001
ENTRYPOINT ["ifec-ingest"]
