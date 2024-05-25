FROM python:3.12-alpine AS base

ENV PYTHONFAULTHANDLER=1 \
	PYTHONUNBUFFERED=1 \
	PYTHONHASHSEED=random \
	PIP_NO_CACHE_DIR=off \
	PIP_DISABLE_PIP_VERSION_CHECK=on \
	PIP_DEFAULT_TIMEOUT=100

RUN apk update && apk add gcc libc-dev libffi-dev

FROM base AS poetry

RUN pip install poetry

WORKDIR /code
COPY poetry.lock pyproject.toml /code/

RUN poetry config virtualenvs.create false && \
	poetry export --without-hashes -f requirements.txt -o requirements.txt

FROM base AS final

ENV OUTPUT=/output \
	WATTPAD_USERNAME=example \
	TOKEN=000000000000000000 \
	MULTITHREAD=false \
	RATELIMIT=20 \
	MAX_RETRIES=30 \
	MAX_STORIES=-1 \
	DEBUG=false

WORKDIR /code

COPY --from=poetry /code/requirements.txt .
RUN pip install -r requirements.txt

COPY templates ./templates
COPY archiver.py .

VOLUME ["/output"]

CMD ["python", "archiver.py"]
