"""Shared slowapi Limiter instance.

Split out from main.py so auth/router.py and twofa/router.py can apply
per-endpoint rate limits without a circular import (main.py imports those
routers).
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def session_rate_limit_key(request: Request) -> str:
    """slowapi key_func: rate-limit per authenticated session, not per IP (foroba#176,
    A9) — so users sharing a NAT/office IP don't share a budget, and a single user can't
    dodge the limit by switching networks. Uses the raw `suite_session` cookie value as
    the key (unique per login session, no need to decode/verify it here); falls back to
    per-IP for unauthenticated requests."""
    token = request.cookies.get("suite_session")
    return token if token else get_remote_address(request)
