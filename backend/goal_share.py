"""Goal what-if projection + signed, expiring, read-only share tokens (Plan AQ D9, ID-07).

The token carries only what the public page shows: goal name, currency, the what-if inputs
and the computed series. It never carries a user id, email or any account data. Format:
``base64url(json).base64url(hmac_sha256)``, key derived from the JWT private key so no new
secret has to be provisioned.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

SHARE_TTL_SECONDS = 7 * 24 * 3600
MAX_MONTHS = 360
NAME_MAX = 80
RATE_MIN_PCT = 0.0
RATE_MAX_PCT = 8.0


class ShareTokenError(ValueError):
    """Token is malformed, tampered with, or expired."""


def project_series(
    saved_cents: int, target_cents: int, monthly_cents: int, rate_pct: float
) -> dict[str, Any]:
    """Month-by-month balance with monthly compounding; stops once the target is reached
    (or after MAX_MONTHS). Integer cents only. Mirrors src/lib/goalProjection.ts."""
    monthly_rate = rate_pct / 100 / 12
    balance = saved_cents
    series = [balance]
    months_to_target: int | None = 0 if balance >= target_cents else None
    month = 0
    while months_to_target is None and month < MAX_MONTHS:
        balance = round(balance * (1 + monthly_rate)) + monthly_cents
        month += 1
        series.append(balance)
        if balance >= target_cents:
            months_to_target = month
    return {"series": series, "months_to_target": months_to_target}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _key() -> bytes:
    from auth.keys import get_keypair
    from config import settings

    private_pem = get_keypair(settings)[0]
    return hashlib.sha256(b"goal-share-v1" + private_pem.encode()).digest()


def _sign(body: str) -> str:
    return _b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())


def build_payload(
    *,
    name: str,
    currency: str,
    saved_cents: int,
    target_cents: int,
    monthly_cents: int,
    rate_pct: float,
    now: float | None = None,
) -> dict[str, Any]:
    now = time.time() if now is None else now
    proj = project_series(saved_cents, target_cents, monthly_cents, rate_pct)
    return {
        "name": name.strip()[:NAME_MAX],
        "currency": currency[:3].upper(),
        "saved_cents": saved_cents,
        "target_cents": target_cents,
        "monthly_cents": monthly_cents,
        "rate_pct": rate_pct,
        "series": proj["series"],
        "months_to_target": proj["months_to_target"],
        "exp": int(now) + SHARE_TTL_SECONDS,
    }


def issue_token(payload: dict[str, Any]) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    return f"{body}.{_sign(body)}"


def verify_token(token: str, *, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    try:
        body, sig = token.split(".", 1)
    except ValueError as exc:
        raise ShareTokenError("malformed") from exc
    if not hmac.compare_digest(sig, _sign(body)):
        raise ShareTokenError("invalid signature")
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ShareTokenError("malformed") from exc
    if not isinstance(payload, dict) or payload.get("exp", 0) < now:
        raise ShareTokenError("expired")
    return payload
