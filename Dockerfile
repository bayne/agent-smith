# Stage 1: Build
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Install the project itself
COPY src/ src/
COPY README.md .
RUN uv sync --frozen --no-dev --no-editable

# Stage 2: Runtime
FROM python:3.14-slim

RUN useradd --create-home app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

USER app

ENTRYPOINT ["agent-smith"]
