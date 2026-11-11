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


def issue_stepup_token(
    user_id: int, app: str, *, auth_time: int | None = None, session_version: int = 1
) -> str:
    """`auth_time` is when the user last proved MFA (kept across refreshes so the window
    has an absolute cap); `sv` is the user's session_version at issue time, so raising
    the floor (password change, revoke-all) stops further refreshes (Plan AU M-1)."""
    private_key, _, kid = keys.get_keypair(settings)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "app": app,
        "typ": "stepup",
        "iat": now,
        "exp": now + timedelta(minutes=settings.stepup_ttl_minutes),
        "auth_time": auth_time if auth_time is not None else int(now.timestamp()),
        "sv": session_version,
    }
    return jwt.encode(payload, private_key, algorithm=_ALGO, headers={"kid": kid})


def verify_stepup_token(token: str, *, expected_app: str) -> dict:
    _, public_key, _ = keys.get_keypair(settings)
    try:
        claims = jwt.decode(
            token, public_key, algorithms=[_ALGO], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as exc:
        raise StepupTokenError(str(exc)) from exc
    if claims.get("typ") != "stepup":
        raise StepupTokenError("not a step-up token")
    if claims.get("app") != expected_app:
        raise StepupTokenError(
            f"Token is scoped to app={claims.get('app')!r}, expected {expected_app!r}"
        )
    return claims


def needs_refresh(claims: dict) -> bool:
    exp = datetime.fromtimestamp(claims["exp"], tz=UTC)
    remaining = exp - datetime.now(UTC)
    return remaining <= timedelta(minutes=settings.stepup_refresh_threshold_minutes)


def issue_stepup_cookies(user_id: int) -> dict[str, str]:
    """Mint stepup_pazuru + stepup_tsumi tokens directly, for callers with no
    interactive browser session to forward cookies from -- scheduled background
    jobs and public-API-key requests (foroba#215).

    This does not weaken the step-up guarantee: Foroba's backend already holds
    the sole signing key and unrestricted authority to mint suite_session for
    any user (that's what login does). The interactive /auth/stepup/verify
    endpoint exists to gate this specific action behind live MFA proof for
    *browser-initiated* requests, where the threat model is a stolen/replayed
    suite_session cookie. Background jobs and API-key calls originate from
    Foroba's own trusted server process, not a browser session that could be
    hijacked, so minting these tokens in-process exercises the same trust
    Foroba already has -- it isn't a new bypass.
    """
    return {
        "pazuru": issue_stepup_token(user_id, "pazuru"),
        "tsumi": issue_stepup_token(user_id, "tsumi"),
    }
