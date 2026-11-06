# Build context is the REPO ROOT (see root docker-compose.yml `build.context: .`), not this
# directory — needed because the frontend depends on the sibling `foroba-ui/` package via
# `"@foroba/ui": "file:../foroba-ui"`, which Docker can only COPY if it's inside the context.

# ── Stage 1: build the shared @foroba/ui design system ──────────────────────
FROM node:22-alpine AS foroba-ui-build
WORKDIR /app/foroba-ui
COPY foroba-ui/package.json foroba-ui/pnpm-lock.yaml foroba-ui/pnpm-workspace.yaml ./
RUN npm install -g pnpm@11.6.0 && pnpm install --frozen-lockfile
COPY foroba-ui/ .
RUN pnpm build

# ── Stage 2: build React frontend ────────────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /app/foroba
COPY --from=foroba-ui-build /app/foroba-ui /app/foroba-ui
COPY foroba/package.json foroba/pnpm-lock.yaml foroba/pnpm-workspace.yaml ./
RUN npm install -g pnpm@11.6.0 && pnpm install --frozen-lockfile
COPY foroba/ .
# Baked into the bundle at build time (Vite inlines import.meta.env.VITE_*) — used by
# AccountsPage/PortfolioPage/AppOnboardingPage to link out to Pazuru/Tsumi's own
# settings pages. Defaults are dev-only; production MUST override via build args
# (see docker-compose.prod.yml) or these links point at localhost for real users.
ARG VITE_PAZURU_APP_URL=http://localhost:5173
ARG VITE_TSUMI_APP_URL=http://localhost:5178
ARG VITE_DEPLOYMENT_MODE=selfhost
ENV VITE_PAZURU_APP_URL=$VITE_PAZURU_APP_URL
ENV VITE_TSUMI_APP_URL=$VITE_TSUMI_APP_URL
ENV VITE_DEPLOYMENT_MODE=$VITE_DEPLOYMENT_MODE
RUN pnpm build

# ── Stage 3: Python backend ──────────────────────────────────────────────────
FROM python:3.12-slim AS backend
WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libsqlcipher-dev && rm -rf /var/lib/apt/lists/*

COPY foroba/backend/requirements.txt .
RUN pip install --no-cache-dir pip==26.2 && pip install --no-cache-dir -r requirements.txt

COPY foroba/backend/ .

# ── Stage 4: Final image ──────────────────────────────────────────────────────
FROM python:3.12-slim AS final
WORKDIR /app

# libsqlcipher1 (runtime .so, not -dev) — the sqlcipher3 wheel compiled in the
# `backend` stage dlopen()s this at import time; the -dev headers aren't needed here.
# The base image's pip (dist-info) and ensurepip wheels would survive the site-packages COPY
# below as stale, vulnerable copies; drop them so only the backend stage's pip 26.2 ships.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libsqlcipher1 && rm -rf /var/lib/apt/lists/* \
 && rm -rf /usr/local/lib/python3.12/site-packages/pip /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
 && rm -f /usr/local/lib/python3.*/ensurepip/_bundled/*.whl

COPY --from=backend /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend /usr/local/bin /usr/local/bin
COPY --from=backend /app/backend /app/backend

COPY --from=frontend-build /app/foroba/dist /app/static

# Plan AU M-5: run as an unprivileged user. Prod volumes must be chown'd to 10001.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app \
 && mkdir -p /data /app/backend/static && chown -R app:app /data /app/backend/static \
 && chmod -R a+rX /app
USER app

ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/data/foroba_identity.db

EXPOSE 8002
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--app-dir", "/app/backend", "--proxy-headers", "--forwarded-allow-ips=172.19.0.0/16"]
