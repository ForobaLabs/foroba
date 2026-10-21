# ADR 005: Internal Service TLS (mTLS trigger)

# ADR-005: Internal Service-to-Service TLS (mTLS trigger)

**Status**: Accepted
**Date**: 2026-07-31

## Context
GL-11.1 requires documenting encryption-in-transit coverage. External TLS (browser ↔
reverse proxy) is done via GL-1.2 (Caddy/nginx + certbot, Cloudflare proxy). What remained
undocumented: the internal service-to-service calls — Foroba↔Pazuru, Foroba↔Tsumi proxy
calls, and JWKS fetches used by `require_auth` in each backend to validate the shared
`suite_session` JWT.

## Decision
Internal service-to-service traffic runs **unencrypted HTTP today**, and this is
acceptable as long as all three backends (Foroba, Pazuru, Tsumi) run as containers on the
**same isolated Docker network on a single host**, with no port mapping that exposes their
internal ports to anything outside that network. Nothing external can observe or
intercept this traffic without first compromising the host itself, at which point mTLS
between containers would not have been the binding constraint anyway.

**Explicit trigger for adding internal mTLS**: the moment any of these backends is moved
to a **separate host** from the others (e.g. horizontal scaling, splitting Tsumi's
market-analysis workload onto its own VPS, or a managed-Postgres/DuckDB service outside
the Docker network) — traffic would then cross a real network boundary and needs mTLS
(mutual cert auth between services) or at minimum a WireGuard/VPN tunnel between hosts.
Do not defer this past that point.

## Consequences
- No implementation work needed until the single-host assumption changes.
- Anyone provisioning a second host for any of the 3 backends must treat mTLS/tunnel setup
  as a blocking prerequisite of that migration, not a follow-up.
- Revisit this ADR the day multi-host deployment is actually planned.

