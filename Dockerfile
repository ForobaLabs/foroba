# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Copy foroba-ui first (local dep)
COPY foroba-ui/ ../foroba-ui/

# Install & build foroba-ui
RUN cd ../foroba-ui && pnpm install --frozen-lockfile && pnpm build

# Copy foroba shell
COPY foroba/package.json foroba/pnpm-lock.yaml ./

RUN pnpm install --frozen-lockfile

COPY foroba/ ./

ARG VITE_PAZURU_API_URL=/pazuru-api
ARG VITE_TSUMI_API_URL=/tsumi-api
ARG VITE_JELI_API_URL=/jeli

RUN pnpm build

# ── Stage 2: serve ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY foroba/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
