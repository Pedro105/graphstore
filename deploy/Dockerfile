# syntax=docker/dockerfile:1.7
#
# Production image for the ContextStore FastAPI backend.
#
# Multi-stage: the builder resolves and installs dependencies with uv straight
# from uv.lock (so the image can never drift from the lockfile), and the final
# runtime stage is a slim Python image carrying only the prebuilt virtualenv and
# the application source -- no uv, no build tools, no secrets.
#
# Build context is the REPO ROOT (so it can see pyproject.toml / uv.lock / src):
#   docker build -f deploy/Dockerfile -t contextstore-backend .

# ---- Builder: install deps + project into a venv via uv -----------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first, from the lockfile + manifest only and without the
# project itself, so editing application code doesn't bust this (slow) layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Then add the source and install the project (hatchling needs README.md too).
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- Runtime: slim image with just Python + the prebuilt venv -----------------
FROM python:3.12-slim-bookworm AS runtime

# Drop root: the app never needs to write outside the venv.
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

# The venv carries an editable install pointing at /app/src, so both are needed
# at the same paths they had in the builder.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

USER app

EXPOSE 8000

# No --reload in production. Bind to all interfaces so Fly's proxy can reach it.
CMD ["uvicorn", "contextstore.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
