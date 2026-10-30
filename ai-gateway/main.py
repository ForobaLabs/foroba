"""ai-gateway: the only service that holds provider credentials and runs PII masking."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

import chat
import consent
import db
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


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
