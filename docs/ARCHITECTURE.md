# Kelen architecture

Kelen is the front door of a three-app suite. This document explains how the pieces fit and why.

## Components

| Component | Path | Responsibility |
| --- | --- | --- |
| Web app | `src/` | React SPA: dashboard, goals, what-if, markets, security settings, admin, Jeli chat and Lab |
| API | `backend/` | FastAPI service: identity, sessions, MFA, net worth, goals, billing, reports, public API |
| AI gateway | `ai-gateway/` | Separate service in front of every LLM call: PII masking, consent, quotas, BYOK, provider routing |
| Sandbox runner | `sandbox-runner/` | Executes model-generated analysis code in a locked-down container |
| Naforo / Yiriba | separate repos | Bank-account and ETF/crypto backends; trust Kelen-minted sessions |

## Identity and sessions

Kelen is the only service that authenticates people. After password and second factor, it mints an **RS256 JWT**
session (`suite_session`). Naforo and Yiriba never see credentials; they verify the token's signature against
Kelen's **JWKS** endpoint and apply their own authorization.

- **Second factors:** passkeys (WebAuthn), TOTP, e-mail OTP, recovery codes. A short-lived MFA ticket binds the
  password step to the second-factor step so the two cannot be replayed separately.
- **Step-up:** sensitive operations in any app return `428` until the user re-verifies; the resulting
  `stepup_<app>` token is scoped to that app and expires quickly.
- **Revocation:** sessions carry a floor; raising it (password change, "sign out everywhere") invalidates older tokens
  in all three apps without a shared session store.
- **Cross-app navigation:** a one-time handoff code lets the browser move between apps on different origins without
  exposing tokens in URLs.
- **CSRF:** state-changing requests are checked against an Origin allow-list in addition to same-site cookies.

## Data

- Each backend owns an **SQLCipher-encrypted SQLite** database; schema changes ship as Alembic migrations and are
  mirrored in the runtime schema initialiser so fresh and upgraded installs end up identical.
- Net worth is computed on read from the apps' own APIs plus Kelen-held liabilities, converted with ECB FX rates
  (cached, refreshed on a schedule).
- Backups are encrypted, copied off-site and pruned by a retention job. Restore is rehearsed, not assumed.

## AI pipeline

```
 user question ─► Kelen API ─► AI gateway ─► (PII masking) ─► provider (local or cloud, BYOK)
                                   │                               │
                              consent · quota                 response
                                   │                               ▼
                                   └────────────────── output guard ─► user
```

1. **Consent and quota** are checked per feature before anything leaves the process.
2. **Masking** replaces names, e-mail addresses, IBANs and similar entities with stable placeholders and restores
   them in the reply.
3. **Providers** are OpenAI-compatible; users can supply their own key or use a local model.
4. The **output guard** compares every monetary figure in a reply with the figures that were actually provided and
   appends the mandatory disclaimer; replies with invented amounts are rejected.
5. **Jeli Lab** lets the model write analysis code. It runs in the sandbox runner: no network, read-only filesystem,
   CPU/memory/time caps, one container per execution.

## Billing and access

Plans are modelled as two axes: **audience** (base / expert) and **tier** (free / premium). Premium-only endpoints
answer `402`, audience-gated ones `403`. Paddle is the merchant of record; webhook signatures are verified and events
are processed idempotently.

## Delivery

GitHub Actions run lint, type-check, unit tests, dependency (OSV) and secret scanning on every change. Services ship
as Docker images behind nginx; a production guard refuses to boot in production with unsafe configuration
(dev auth bypass on, weak internal token, non-HTTPS or wildcard origins, insecure cookies).
