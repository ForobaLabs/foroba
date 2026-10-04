"""Shared slowapi Limiter instance.

Split out from main.py so auth/router.py and twofa/router.py can apply
per-endpoint rate limits without a circular import (main.py imports those
routers).
"""

from __future__ import annotations

from fastapi import Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """429 handler that also sends `Retry-After` (seconds until the window resets).

    slowapi only injects it when `headers_enabled=True`, which in turn requires every
    endpoint to accept a `response` param; computing it here keeps endpoints untouched.
    """
    response = _rate_limit_exceeded_handler(request, exc)
    response.headers["Retry-After"] = str(int(exc.limit.limit.get_expiry()))
    return response


def session_rate_limit_key(request: Request) -> str:
    """slowapi key_func: rate-limit per authenticated session, not per IP (foroba#176,
    A9) — so users sharing a NAT/office IP don't share a budget, and a single user can't
    dodge the limit by switching networks. Uses the raw `suite_session` cookie value as
    the key (unique per login session, no need to decode/verify it here); falls back to
    per-IP for unauthenticated requests."""
    token = request.cookies.get("suite_session")
    return token if token else get_remote_address(request)
