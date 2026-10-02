"""Paddle webhook signature: header `ts=<unix>;h1=<hex>`, HMAC-SHA256 of `ts:raw_body`."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

TOLERANCE_SECONDS = 300


class SignatureError(Exception):
    pass


def verify_signature(header: str, body: bytes, secret: str, *, now: datetime | None = None) -> None:
    if not secret:
        raise SignatureError("webhook secret not configured")
    ts_raw: str | None = None
    h1s: list[str] = []
    for part in (header or "").split(";"):
        key, _, value = part.partition("=")
        if key.strip() == "ts":
            ts_raw = value.strip()
        elif key.strip() == "h1":
            h1s.append(value.strip())
    if ts_raw is None or not h1s:
        raise SignatureError("malformed signature header")
    try:
        ts = int(ts_raw)
    except ValueError as exc:
        raise SignatureError("malformed timestamp") from exc
    current = (now or datetime.now(UTC)).timestamp()
    if abs(current - ts) > TOLERANCE_SECONDS:
        raise SignatureError("timestamp outside tolerance")
    expected = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    # h1 may appear more than once while Paddle rotates the secret.
    if not any(hmac.compare_digest(expected, h1) for h1 in h1s):
        raise SignatureError("signature mismatch")
