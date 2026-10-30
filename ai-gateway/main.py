"""ai-gateway: the only service that holds provider credentials and runs PII masking."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import byok
import chat
import consent
import db
import gdpr
import prefs
import quota
import usage


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = db.connect()
    quota.load_breaker(conn)
    conn.close()
    yield


app = FastAPI(
    title="ai-gateway",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.include_router(consent.router)
app.include_router(prefs.router)
app.include_router(chat.router)
app.include_router(usage.router)
app.include_router(byok.router)
app.include_router(gdpr.router)


@app.exception_handler(RequestValidationError)
async def _validation_error(_, exc: RequestValidationError) -> JSONResponse:
    """422 without `input`/`ctx`: a rejected body may hold a BYOK key and must never be echoed."""
    detail = [{k: v for k, v in e.items() if k not in ("input", "ctx")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
