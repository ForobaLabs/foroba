"""Short-lived, app-scoped step-up tokens (RS256, same keypair as suite_session).

Issued after a user re-proves a second factor when switching into Pazuru/Tsumi, or when
returning to any app after being idle. Verified locally by Pazuru/Tsumi via the same JWKS
endpoint they already trust for suite_session (kid matches — one keypair, two token kinds
distinguished by an `app` claim and shorter TTL). Idle timeout falls out of this token's own
fixed TTL: as long as the user is active, the app calls /auth/stepup/refresh before expiry to
slide the window forward; if idle, no refresh happens and the token simply expires.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from auth import keys
from config import settings

_ALGO = "RS256"


class StepupTokenError(Exception):
    """Raised for any invalid/expired/mismatched step-up token."""


def issue_stepup_token(user_id: int, app: str) -> str:
    private_key, _, kid = keys.get_keypair(settings)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "app": app,
        "iat": now,
        "exp": now + timedelta(minutes=settings.stepup_ttl_minutes),
    }
    return jwt.encode(payload, private_key, algorithm=_ALGO, headers={"kid": kid})


def verify_stepup_token(token: str, *, expected_app: str) -> dict:
    _, public_key, _ = keys.get_keypair(settings)
    try:
        claims = jwt.decode(token, public_key, algorithms=[_ALGO])
    except jwt.PyJWTError as exc:
        raise StepupTokenError(str(exc)) from exc
    if claims.get("app") != expected_app:
        raise StepupTokenError(
            f"Token is scoped to app={claims.get('app')!r}, expected {expected_app!r}"
        )
    return claims


def needs_refresh(claims: dict) -> bool:
    exp = datetime.fromtimestamp(claims["exp"], tz=UTC)
    remaining = exp - datetime.now(UTC)
    return remaining <= timedelta(minutes=settings.stepup_refresh_threshold_minutes)
