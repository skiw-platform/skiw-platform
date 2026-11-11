FROM ghcr.io/astral-sh/uv:0.11.24@sha256:99ea34acedc870ba4ad11a1f540a1c04267c9f30aadc465a94406f52dfda2c36 AS uv

FROM node:26.11.1-slim@sha256:193fe51b64e77981119c98c2002c9e32a70e2f006fb4d25068ce0558998917f0 AS web

# pnpm comes from the packageManager field in package.json (pnpm 11.6.0).
RUN corepack enable
WORKDIR /build
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY web ./web
RUN pnpm install --frozen-lockfile && pnpm -C web build

FROM python:3.12.15-alpine@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/.venv/bin:$PATH" \
    PYTHONPATH=/srv/app

# REMOVE-WHEN-UPSTREAM-REBUILDS (DECISIONS 2026-11-11, "base images krb5-libs"): krb5-libs (pulled in
# by libtirpc) is 1.22.2-r1 in the pinned base, with 16 fixed HIGH CVEs, and Docker Hub has no
# rebuild of the python alpine tag yet. `>=` is deliberate: an exact pin breaks when Alpine's index
# drops the version.
RUN apk add --no-cache "krb5-libs>=1.22.3-r0"

RUN adduser -S -u 10001 -h /nonexistent -H -s /sbin/nologin skiw

WORKDIR /srv
COPY pyproject.toml uv.lock .python-version ./
# uv is mounted for this step only, so the image ships without it.
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    uv sync --locked --no-dev --no-install-project

COPY app ./app
COPY --from=web /build/web/dist ./web/dist
# Fails the build if the manifest is missing or malformed, or names a file that is not there.
RUN python -m shell.verify_dist /srv/web/dist

USER skiw
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn_worker.UvicornWorker", "-b", "0.0.0.0:8000"]
