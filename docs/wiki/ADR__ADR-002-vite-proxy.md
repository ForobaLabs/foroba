# ADR 002 vite proxy

# ADR-002: Vite proxy for microservice APIs

**Status**: Accepted  
**Date**: 2026-06-15

## Context
Foroba needs to fetch data from Pazuru (port 8001) and Tsumi (port 8000). Direct cross-origin requests in dev mode hit CORS restrictions.

## Decision
Use Vite `server.proxy` to rewrite:
- `/pazuru-api/*` → `VITE_PAZURU_API_URL/*`
- `/tsumi-api/*` → `VITE_TSUMI_API_URL/*`

In production, the same routing is handled by nginx/reverse-proxy.

## Consequences
- Zero CORS issues in development.
- API helpers always call `/pazuru-api/...` and `/tsumi-api/...` — same path in dev and production.

