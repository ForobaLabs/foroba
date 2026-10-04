"""429 responses must carry Retry-After (Plan AK / OOS-1)."""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from rate_limit import limiter, rate_limit_exceeded_handler


def test_429_carries_retry_after():
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    @limiter.limit("1/minute")
    def ping(request: Request):
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/ping").status_code == 200
    limited = client.get("/ping")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"
