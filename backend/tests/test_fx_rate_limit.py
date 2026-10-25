"""GET /fx/rates is unauthenticated and refreshes from upstream, so it is rate-limited
(Plan AU L-4)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

import fx_router
from auth.conn import get_conn
from rate_limit import limiter, rate_limit_exceeded_handler


def test_fx_rates_is_rate_limited(monkeypatch):
    limiter.reset()
    monkeypatch.setattr(fx_router.fx_service, "refresh_latest_rates", lambda conn: None)
    monkeypatch.setattr(fx_router, "_get_latest_rates", lambda conn: {"USD": 1.1})
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.include_router(fx_router.router)
    app.dependency_overrides[get_conn] = lambda: None
    c = TestClient(app)
    codes = [c.get("/fx/rates").status_code for _ in range(61)]
    assert codes[:60] == [200] * 60
    assert codes[60] == 429
    limiter.reset()
