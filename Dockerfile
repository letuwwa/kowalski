ARG PYTHON_VERSION=3.14.7

FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

RUN addgroup --system app \
    && adduser --system --ingroup app --home /home/app app

USER app

EXPOSE 5000

ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]
