"""ai-gateway: the only service that holds provider credentials and runs PII masking."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

import consent
import db
import prefs


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.connect().close()
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


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
