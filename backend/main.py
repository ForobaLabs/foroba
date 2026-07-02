"""Foroba Jeli backend — FastAPI microservice for unified AI assistant.

Start:
    uvicorn main:app --host 127.0.0.1 --port 8002 --reload
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from config import settings

RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5175,http://localhost:5173,http://localhost:5174,http://localhost:5178",
).split(",")
limiter = Limiter(key_func=get_remote_address)
from db import seed_mock_users as _seed
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    init_settings(conn)


class Personality(BaseModel):
    tone: Annotated[int, Field(ge=0, le=10)] = 5
    expertise: Annotated[int, Field(ge=0, le=10)] = 5


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    user_name: str = "User"
    personality: Personality = Personality()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "foroba-jeli", "version": "0.1.0"}


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


@app.post("/chat")
async def jeli_chat(req: ChatRequest,
                    _: dict = Depends(get_current_user)) -> StreamingResponse:
    """Stream a Jeli response for the given message.

    Gathers context from Pazuru + Tsumi, builds the system prompt,
    then streams the Ollama response as plain text chunks (SSE-compatible).
    """
    pazuru_ctx, tsumi_ctx = await gather_context(
        settings.pazuru_api_url,
        settings.tsumi_api_url,
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
