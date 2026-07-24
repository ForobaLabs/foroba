"""Password hashing (argon2id) and JWT helpers for suite authentication."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt as _bcrypt_lib
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_ph = PasswordHasher()  # argon2id, secure defaults
_ALGO = "RS256"


def hash_password(plain: str) -> str:
    """Hash a password with argon2id."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password. Supports both legacy bcrypt ($2b$) and argon2 ($argon2) hashes."""
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        try:
            return _bcrypt_lib.checkpw(plain.encode(), hashed.encode())
        except Exception:
            return False
    try:
        _ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """True if this hash should be upgraded to argon2 on next login."""
    return hashed.startswith("$2b$") or hashed.startswith("$2a$") or _ph.check_needs_rehash(hashed)


def create_token(
    user_id: int, private_key: str, ttl_minutes: int, *,
    tier: str = "free", audience: str = "base", is_admin: bool = False, kid: str | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
        "tier": tier,
        "audience": audience,
        "is_admin": is_admin,
    }
    headers = {"kid": kid} if kid else None
    return jwt.encode(payload, private_key, algorithm=_ALGO, headers=headers)


def decode_token(token: str, public_key: str) -> dict:
    return jwt.decode(token, public_key, algorithms=[_ALGO])
