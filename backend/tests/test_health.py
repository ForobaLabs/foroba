"""Health endpoint tests (TI-B item 1, foroba#152)."""
import pytest
from fastapi.testclient import TestClient

import main
from auth.dependencies import require_admin


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # /health and /health/detailed are rate-limited (1/second) — reset between
    # tests in this module so they don't rate-limit each other when run together.
    main.limiter.reset()
    yield
    main.limiter.reset()


def test_health_returns_ok():
    client = TestClient(main.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["db"] == "ok"


def test_health_returns_503_when_db_down(monkeypatch):
    async def _fail_check_db():
        return "down"

    monkeypatch.setattr(main, "_check_db", _fail_check_db)
    client = TestClient(main.app)
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_health_detailed_requires_admin():
    client = TestClient(main.app)
    resp = client.get("/health/detailed")
    assert resp.status_code == 401


def test_health_detailed_ok_for_admin():
    main.app.dependency_overrides[require_admin] = lambda: {"id": 1, "is_admin": True}
    client = TestClient(main.app)
    resp = client.get("/health/detailed")
    main.app.dependency_overrides.pop(require_admin, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["checks"]["db"] == "ok"
    assert "version" in body


def test_health_rate_limited_after_burst():
    client = TestClient(main.app)
    first = client.get("/health")
    second = client.get("/health")

    assert first.status_code == 200
    assert second.status_code == 429
