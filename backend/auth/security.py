"""Password hashing (bcrypt) and JWT helpers for suite authentication."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALGO = "HS256"


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_token(
    user_id: int, secret: str, ttl_minutes: int, *,
    tier: str = "free", audience: str = "base", is_admin: bool = False
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
        "tier": tier,
        "audience": audience,
        "is_admin": is_admin,
    }
    return jwt.encode(payload, secret, algorithm=_ALGO)


def decode_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=[_ALGO])
