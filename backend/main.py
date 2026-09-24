"""Foroba Jeli backend — FastAPI microservice for unified AI assistant.

Start:
    uvicorn main:app --host 127.0.0.1 --port 8002 --reload
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

import db
import markets_service
import networth_service
import notification_service
import settings_store
from admin_router import router as admin_router
from auth import keys
from auth.api_keys_router import router as api_keys_router
from auth.dependencies import get_current_user, require_admin
from auth.entitlements_router import require_feature
from auth.entitlements_router import router as entitlements_router
from auth.router import get_conn
from auth.router import router as auth_router
from auth.token_router import router as token_router
from auth.webhooks_router import router as webhooks_router
from backup_scheduler import start_backup_scheduler
from config import settings
from db import purge_mock_users as _purge
from db import seed_demo_household as _seed_household
from db import seed_mock_users as _seed
from fx_router import router as fx_router
from fx_scheduler import start_fx_scheduler
from goals_router import router as goals_router
from handoff_router import router as handoff_router
from jeli_service import build_system_prompt, gather_context, stream_chat
from lab_router import router as lab_router
from monthly_report_router import router as monthly_report_router
from observability import init_error_tracking
from onboarding.router import router as onboarding_router
from passkeys.router import router as passkeys_router
from public_api_router import router as public_api_router
from rate_limit import limiter, session_rate_limit_key
from report_scheduler import start_report_scheduler
from retention_job import start_retention_scheduler
from settings_store import init_settings
from stepup import issue_stepup_cookies
from stepup_router import router as stepup_router
from twofa.router import router as twofa_router
from webhook_dispatch_job import start_webhook_dispatch_scheduler
from whatif_router import router as whatif_router

RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5175,http://localhost:5173,http://localhost:5174,http://localhost:5178",
).split(",")
ENABLE_API_DOCS = os.getenv("ENABLE_API_DOCS", "true").lower() == "true"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
init_error_tracking(settings.glitchtip_dsn)

app = FastAPI(
    title="Foroba Jeli API",
    description="Unified local LLM assistant — cross-domain financial advisor",
    version="0.1.0",
    docs_url="/docs" if ENABLE_API_DOCS else None,
    redoc_url="/redoc" if ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_API_DOCS else None,
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
    # CL-2.9: X-Stepup-Token must be accessible by JS in cross-origin responses
    expose_headers=["X-Stepup-Token"],
)

_static_dir = Path(__file__).resolve().parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.include_router(auth_router)
app.include_router(token_router)
app.include_router(entitlements_router)
app.include_router(onboarding_router)
app.include_router(admin_router)
app.include_router(lab_router)
app.include_router(twofa_router)
app.include_router(passkeys_router)
app.include_router(stepup_router)
app.include_router(handoff_router)
app.include_router(whatif_router)
app.include_router(goals_router)
app.include_router(monthly_report_router)
app.include_router(fx_router)
app.include_router(api_keys_router)
app.include_router(webhooks_router)
app.include_router(public_api_router)


@app.on_event("startup")
def _startup() -> None:
    conn = get_conn()
    # foroba#214: mock/seed accounts must never be created in hosted (prod) mode.
    # foroba#254: additionally purge any dev seed rows that may have been created
    # before the hosted guard existed — ensures known-password accounts are scrubbed
    # from the prod DB on every startup when deployment_mode == "hosted".
    if settings.deployment_mode == "hosted":
        removed = _purge(conn)
        if removed:
            logger.warning("purge_mock_users: removed dev seed accounts %s", removed)
    elif settings.seed_mock_users:
        _seed(conn)
        _seed_household(conn)
    init_settings(conn)
    start_report_scheduler()
    start_fx_scheduler()
    start_webhook_dispatch_scheduler()
    start_backup_scheduler()
    start_retention_scheduler()


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
async def health_detailed(
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> dict:
    db_status = await _check_db()
    drift = settings_store.check_drift(conn)
    return {
        "status": "ok" if db_status == "ok" and not drift else "degraded",
        "checks": {
            "db": db_status,
            "settings_drift": "ok" if not drift else "drifted",
        },
        "version": "0.1.0",
        "dependencies": {},
        "settings_drift": drift,
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
    stepup_tsumi: str | None = Cookie(default=None),
    user: dict = Depends(require_feature("markets.sentiment")),
) -> dict:
    """Aggregate Tsumi rating + sentiment + top movers for one symbol.

    FOR-D01: gated server-side on markets.sentiment (tier=premium) — this route
    delivers the premium sentiment field, unlike /markets/overview which never
    touches it and stays free/anonymous. Read-only superapp surface. Degrades
    gracefully if Tsumi is offline: failed sections are null and `degraded` is
    true; never returns 500.
    """
    return await markets_service.fetch_snapshot(
        symbol, asset_class, cookie=suite_session, stepup_tsumi=stepup_tsumi
    )


@app.get("/markets/overview")
async def markets_overview(
    asset_class: str = Query("crypto"),
    suite_session: str | None = Cookie(default=None),
    stepup_tsumi: str | None = Cookie(default=None),
) -> dict:
    """Top gainers/losers + news for the Markets landing page (FB-3).

    Read-only superapp surface. Degrades gracefully if Tsumi is offline.
    """
    return await markets_service.fetch_overview(
        asset_class, cookie=suite_session, stepup_tsumi=stepup_tsumi
    )


@app.get("/networth/summary")
async def networth_summary(
    days: int = 365,
    include_manual_assets: bool = True,
    include_debts: bool = False,
    user: dict = Depends(get_current_user),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    """Aggregate bank net worth (Pazuru) + investment portfolio (Tsumi), optionally
    including manual assets (foroba#157, extended foroba#164) and manual debts
    (TI-D item 3 Plan 1 debts module, pazuru#99), into one unified total. Requires
    auth — this is per-user financial data, unlike the public-ish /markets/*
    surface. Degrades gracefully if either upstream is offline: failed sections
    are null and `degraded` is true; never returns 500.

    Step-up tokens are minted server-side (same pattern as /auth/account/export)
    because stepup_pazuru/stepup_tsumi cookies are set on their respective subdomains
    and are never forwarded to foroba-app.duckdns.org by the browser (DuckDNS PSL
    treats each subdomain independently)."""
    stepup = issue_stepup_cookies(user["id"])
    return await networth_service.fetch_networth(
        days,
        cookie=suite_session,
        stepup_pazuru=stepup["pazuru"],
        stepup_tsumi=stepup["tsumi"],
        include_manual_assets=include_manual_assets,
        include_debts=include_debts,
    )


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
    stepup = issue_stepup_cookies(user["id"])
    return await notification_service.generate_notifications(
        conn, user["id"], cookie=suite_session, stepup_pazuru=stepup["pazuru"]
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
@limiter.limit("20/minute", key_func=session_rate_limit_key)
async def jeli_chat(
    request: Request,
    req: ChatRequest,
    _: dict = Depends(get_current_user),
    suite_session: str | None = Cookie(default=None),
    stepup_pazuru: str | None = Cookie(default=None),
    stepup_tsumi: str | None = Cookie(default=None),
) -> StreamingResponse:
    """Stream a Jeli response for the given message.

    Gathers context from Pazuru + Tsumi, builds the system prompt,
    then streams the Ollama response as plain text chunks (SSE-compatible).
    """
    pazuru_ctx, tsumi_ctx = await gather_context(
        settings.pazuru_api_url,
        settings.tsumi_api_url,
        cookie=suite_session,
        stepup_pazuru=stepup_pazuru,
        stepup_tsumi=stepup_tsumi,
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
