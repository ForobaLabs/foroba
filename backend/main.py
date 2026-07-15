"""Foroba Jeli backend — FastAPI microservice for unified AI assistant.

Start:
    uvicorn main:app --host 127.0.0.1 --port 8002 --reload
"""
from __future__ import annotations

import logging
import os
import sqlite3
from typing import Annotated

import asyncio

from fastapi import Cookie, Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from config import settings
from observability import init_error_tracking
from auth import keys
from auth.dependencies import require_admin
from rate_limit import limiter

RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5175,http://localhost:5173,http://localhost:5174,http://localhost:5178",
).split(",")
import db
from db import seed_demo_household as _seed_household, seed_mock_users as _seed
from auth.router import router as auth_router, get_conn
from auth.dependencies import get_current_user
from auth.entitlements_router import router as entitlements_router
from onboarding.router import router as onboarding_router
from admin_router import router as admin_router
from lab_router import router as lab_router
from twofa.router import router as twofa_router
from settings_store import init_settings
from jeli_service import build_system_prompt, gather_context, stream_chat
import markets_service
import networth_service
import notification_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
init_error_tracking(settings.glitchtip_dsn)

app = FastAPI(
    title="Foroba Jeli API",
    description="Unified local LLM assistant — cross-domain financial advisor",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth_router)
app.include_router(entitlements_router)
app.include_router(onboarding_router)
app.include_router(admin_router)
app.include_router(lab_router)
app.include_router(twofa_router)


@app.on_event("startup")
def _startup() -> None:
    conn = get_conn()
    if settings.seed_mock_users:
        _seed(conn)
        _seed_household(conn)
    init_settings(conn)


class Personality(BaseModel):
    tone: Annotated[int, Field(ge=0, le=10)] = 5
    expertise: Annotated[int, Field(ge=0, le=10)] = 5


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    user_name: str = "User"
    personality: Personality = Personality()


async def _check_db() -> str:
    def _query() -> None:
        conn = get_conn()
        conn.execute("SELECT 1")

    try:
        await asyncio.wait_for(asyncio.to_thread(_query), timeout=2.0)
        return "ok"
    except Exception:
        return "down"


@app.get("/health")
@limiter.limit("1/second")
async def health(request: Request) -> JSONResponse:
    db_status = await _check_db()
    ok = db_status == "ok"
    body = {
        "status": "ok" if ok else "degraded",
        "checks": {"db": db_status},
        "version": "0.1.0",
    }
    return JSONResponse(content=body, status_code=200 if ok else 503)


@app.get("/health/detailed")
@limiter.limit("1/second")
async def health_detailed(request: Request, _: dict = Depends(require_admin)) -> dict:
    db_status = await _check_db()
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "checks": {"db": db_status},
        "version": "0.1.0",
        "dependencies": {},
    }


@app.get("/.well-known/jwks.json", include_in_schema=False)
async def jwks() -> dict:
    """Public JWKS — lets Pazuru/Tsumi verify Foroba-issued RS256 tokens without ever
    holding the private key (foroba#149)."""
    import json

    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from jwt.algorithms import RSAAlgorithm

    _, public_pem, kid = keys.get_keypair(settings)
    key_obj = load_pem_public_key(public_pem.encode())
    jwk = json.loads(RSAAlgorithm.to_jwk(key_obj))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


@app.get("/markets/snapshot")
async def markets_snapshot(
    symbol: str = Query(..., min_length=1, max_length=32),
    asset_class: str = Query("crypto"),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    """Aggregate Tsumi rating + sentiment + top movers for one symbol.

    Read-only superapp surface. Degrades gracefully if Tsumi is offline:
    failed sections are null and `degraded` is true; never returns 500.
    """
    return await markets_service.fetch_snapshot(
        symbol, asset_class, cookie=suite_session
    )


@app.get("/markets/overview")
async def markets_overview(
    asset_class: str = Query("crypto"),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    """Top gainers/losers + news for the Markets landing page (FB-3).

    Read-only superapp surface. Degrades gracefully if Tsumi is offline.
    """
    return await markets_service.fetch_overview(asset_class, cookie=suite_session)


@app.get("/networth/summary")
async def networth_summary(
    days: int = 365,
    _: dict = Depends(get_current_user),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    """Aggregate bank net worth (Pazuru) + investment portfolio (Tsumi) into
    one unified total (foroba#157). Requires auth — this is per-user financial
    data, unlike the public-ish /markets/* surface. Degrades gracefully if
    either upstream is offline: failed sections are null and `degraded` is
    true; never returns 500."""
    return await networth_service.fetch_networth(days, cookie=suite_session)


@app.get("/notifications")
async def list_notifications(
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    """Active (non-dismissed) alerts for the current user (foroba#158):
    low balance, goal reached, recurring payment increased, unusual
    transaction. Deterministic checks over Pazuru data — never LLM-based.
    Degrades gracefully if Pazuru is offline (empty items, degraded=true)."""
    return await notification_service.generate_notifications(
        conn, user["id"], cookie=suite_session
    )


@app.post("/notifications/{notif_key}/dismiss")
async def dismiss_notification(
    notif_key: str,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Permanently suppress one alert instance from resurfacing."""
    db.dismiss_notification(conn, user["id"], notif_key)
    return {"dismissed": True}


@app.post("/chat")
async def jeli_chat(req: ChatRequest,
                    _: dict = Depends(get_current_user),
                    suite_session: str | None = Cookie(default=None)) -> StreamingResponse:
    """Stream a Jeli response for the given message.

    Gathers context from Pazuru + Tsumi, builds the system prompt,
    then streams the Ollama response as plain text chunks (SSE-compatible).
    """
    pazuru_ctx, tsumi_ctx = await gather_context(
        settings.pazuru_api_url,
        settings.tsumi_api_url,
        cookie=suite_session,
    )
    system_prompt = build_system_prompt(
        pazuru_context=pazuru_ctx,
        tsumi_context=tsumi_ctx,
        user_name=req.user_name,
        tone=req.personality.tone,
        expertise=req.personality.expertise,
    )

    async def generate():
        async for chunk in stream_chat(system_prompt, req.message):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
