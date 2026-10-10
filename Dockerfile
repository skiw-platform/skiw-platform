FROM ghcr.io/astral-sh/uv:0.11.24@sha256:99ea34acedc870ba4ad11a1f540a1c04267c9f30aadc465a94406f52dfda2c36 AS uv

FROM node:24.21.0-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS web

# pnpm comes from the packageManager field in package.json (pnpm 11.6.0).
RUN corepack enable
WORKDIR /build
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY web ./web
RUN pnpm install --frozen-lockfile && pnpm -C web build

FROM python:3.12.15-alpine@sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/.venv/bin:$PATH" \
    PYTHONPATH=/srv/app

RUN adduser -S -u 10001 -h /nonexistent -H -s /sbin/nologin skiw

WORKDIR /srv
COPY pyproject.toml uv.lock .python-version ./
# uv is mounted for this step only, so the image ships without it.
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    uv sync --locked --no-dev --no-group infra --no-install-project

COPY app ./app
COPY --from=web /build/web/dist ./web/dist
# Fails the build if the manifest is missing or malformed, or names a file that is not there.
RUN python -m shell.verify_dist /srv/web/dist

USER skiw
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn_worker.UvicornWorker", "-b", "0.0.0.0:8000"]
