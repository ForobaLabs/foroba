# Build context is the REPO ROOT (see root docker-compose.yml `build.context: .`), not this
# directory — needed because the frontend depends on the sibling `foroba-ui/` package via
# `"@foroba/ui": "file:../foroba-ui"`, which Docker can only COPY if it's inside the context.

# ── Stage 1: build the shared @foroba/ui design system ──────────────────────
FROM node:22-alpine AS foroba-ui-build
WORKDIR /app/foroba-ui
COPY foroba-ui/package.json foroba-ui/pnpm-lock.yaml foroba-ui/pnpm-workspace.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY foroba-ui/ .
RUN pnpm build

# ── Stage 2: build React frontend ────────────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /app/foroba
COPY --from=foroba-ui-build /app/foroba-ui /app/foroba-ui
COPY foroba/package.json foroba/pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
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
RUN pip install --no-cache-dir -r requirements.txt

COPY foroba/backend/ .

# ── Stage 4: Final image ──────────────────────────────────────────────────────
FROM python:3.12-slim AS final
WORKDIR /app

# libsqlcipher1 (runtime .so, not -dev) — the sqlcipher3 wheel compiled in the
# `backend` stage dlopen()s this at import time; the -dev headers aren't needed here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libsqlcipher1 && rm -rf /var/lib/apt/lists/*

COPY --from=backend /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend /usr/local/bin /usr/local/bin
COPY --from=backend /app/backend /app/backend

COPY --from=frontend-build /app/foroba/dist /app/static

RUN mkdir -p /data

ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/data/foroba_identity.db

EXPOSE 8002
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--app-dir", "/app/backend", "--proxy-headers", "--forwarded-allow-ips=172.19.0.0/16"]
