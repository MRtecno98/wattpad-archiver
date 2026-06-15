# syntax=docker/dockerfile:1
# check=skip=SecretsUsedInArgOrEnv

FROM python:3.12-alpine AS base

ENV PYTHONFAULTHANDLER=1 \
	PYTHONUNBUFFERED=1 \
	PYTHONHASHSEED=random \
	PIP_NO_CACHE_DIR=off \
	PIP_DISABLE_PIP_VERSION_CHECK=on \
	PIP_DEFAULT_TIMEOUT=100

RUN apk update && apk add gcc libc-dev libffi-dev

FROM base AS uv

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY templates ./templates
COPY archiver.py .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM base AS final

ENV OUTPUT=/output \
	WATTPAD_USERNAME=example \
	TOKEN=000000000000000000 \
	MULTITHREAD=false \
	RATELIMIT=20 \
	MAX_RETRIES=30 \
	MAX_STORIES=-1 \
	DEBUG=false

WORKDIR /app

COPY --from=uv /app/.venv /app/.venv
COPY --from=uv /app /app

ENV PATH="/app/.venv/bin:$PATH"

VOLUME ["/output"]

CMD ["python", "archiver.py"]
