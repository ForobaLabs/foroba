"""Short-lived MFA tickets binding the second login factor to a verified password (PB-014).

/login and /token return one when the account has a second factor; the 2FA, email-OTP-send
and recovery-code endpoints require it, so knowing an email is never enough to reach the
second step. Same RS256 keypair as suite_session, but `typ="mfa_pending"`, which every
session verifier (Foroba, Pazuru, Tsumi) rejects. `sv` pins the user's session_version, so a
password reset or revoke-all voids outstanding tickets.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, Request, Response, status

from auth import keys
from config import settings

_ALGO = "RS256"
_TYP = "mfa_pending"
TICKET_TTL_SECONDS = 300
COOKIE_NAME = "mfa_ticket"


class MfaTicketError(Exception):
    """Raised for any invalid/expired/mismatched MFA ticket."""


def issue_mfa_ticket(user_id: int, session_version: int = 1) -> str:
    private_key, _, kid = keys.get_keypair(settings)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "typ": _TYP,
        "iss": "foroba",
        "iat": now,
        "exp": now + timedelta(seconds=TICKET_TTL_SECONDS),
        "sv": session_version,
    }
    return jwt.encode(payload, private_key, algorithm=_ALGO, headers={"kid": kid})


def verify_mfa_ticket(token: str, user: dict) -> dict:
    _, public_key, _ = keys.get_keypair(settings)
    try:
        claims = jwt.decode(
            token, public_key, algorithms=[_ALGO], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as exc:
        raise MfaTicketError(str(exc)) from exc
    if claims.get("typ") != _TYP:
        raise MfaTicketError("not an MFA ticket")
    if claims.get("sub") != str(user["id"]):
        raise MfaTicketError("ticket issued for another user")
    if claims.get("sv") != user.get("session_version", 1):
        raise MfaTicketError("ticket predates a session revocation")
    return claims


def require_mfa_ticket(
    request: Request, body_ticket: str | None, user: dict | None, *, allow_cookie: bool = True
) -> None:
    """Raise 401 unless a valid ticket for `user` is in the body or (browser flow) the cookie."""
    token = body_ticket or (request.cookies.get(COOKIE_NAME) if allow_cookie else None)
    if user is None or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "MFA session expired, sign in again")
    try:
        verify_mfa_ticket(token, user)
    except MfaTicketError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "MFA session expired, sign in again"
        ) from None


def set_ticket_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=TICKET_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_ticket_cookie(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME, path="/", httponly=True, samesite="strict", secure=settings.cookie_secure
    )
