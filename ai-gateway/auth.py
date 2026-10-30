"""Caller authentication: backend-to-gateway shared token + forwarded Foroba session JWT."""

import hmac
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import jwt
from fastapi import Header, HTTPException, Request

from config import get_settings


@dataclass(frozen=True)
class Caller:
    user_id: int
    tier: Literal["free", "premium"]
    is_admin: bool
    ip: str | None = None


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(
        get_settings().foroba_jwks_url, cache_keys=True, lifespan=3600
    )


def _check_gateway_token(supplied: str | None) -> None:
    expected = get_settings().ai_gateway_token
    if not supplied or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="invalid gateway token")


def require_internal(x_ai_gateway_token: str | None = Header(default=None)) -> None:
    _check_gateway_token(x_ai_gateway_token)


def require_caller(
    request: Request,
    x_ai_gateway_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> Caller:
    _check_gateway_token(x_ai_gateway_token)
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        key = _jwks_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer="foroba",
            options={"require": ["exp", "sub", "iss"]},
        )
        if claims.get("typ") != "session":
            raise jwt.InvalidTokenError("not a session token")
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="invalid session token") from None
    tier = "premium" if claims.get("tier") == "premium" else "free"
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() or (request.client.host if request.client else None)
    return Caller(
        user_id=user_id, tier=tier, is_admin=bool(claims.get("is_admin")), ip=ip
    )
