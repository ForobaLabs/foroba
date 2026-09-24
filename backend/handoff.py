"""Same-origin session handoff tokens (Plan U, pazuru#150 — DuckDNS PSL cross-domain
cookie scoping).

`suite_session`/`stepup_<app>` are set by Foroba's backend and never reach
Pazuru/Tsumi's origins, since every `*.duckdns.org` subdomain is its own
registrable domain per the Public Suffix List. A handoff token is a short-lived,
single-use RS256 JWT (same keypair as suite_session/stepup) that carries the
already-valid session/stepup token VALUES as claims; the target app's own
/auth/handoff endpoint verifies it via the existing JWKS client it already
trusts, then simply Set-Cookies those embedded values onto its own origin.
No new session concept is introduced on the target side.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from auth import keys
from config import settings

_ALGO = "RS256"
_HANDOFF_TTL_SECONDS = 30
VALID_APPS = {"pazuru", "tsumi"}


class HandoffTokenError(Exception):
    """Raised for any invalid/expired/mismatched handoff token."""


def issue_handoff_token(
    *, user_id: int, app: str, redirect: str, sess: str, stepup: str | None
) -> str:
    if app not in VALID_APPS:
        raise ValueError(f"unknown handoff target app {app!r}")
    private_key, _, kid = keys.get_keypair(settings)
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "typ": "handoff",
        "app": app,
        "redirect": redirect,
        "sess": sess,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=_HANDOFF_TTL_SECONDS),
    }
    if stepup:
        claims["stepup"] = stepup
    return jwt.encode(claims, private_key, algorithm=_ALGO, headers={"kid": kid})


def verify_handoff_token(token: str, *, expected_app: str) -> dict:
    _, public_key, _ = keys.get_keypair(settings)
    try:
        claims = jwt.decode(token, public_key, algorithms=[_ALGO])
    except jwt.PyJWTError as exc:
        raise HandoffTokenError(str(exc)) from exc
    if claims.get("typ") != "handoff":
        raise HandoffTokenError("Not a handoff token")
    if claims.get("app") != expected_app:
        raise HandoffTokenError(
            f"Token is scoped to app={claims.get('app')!r}, expected {expected_app!r}"
        )
    return claims
