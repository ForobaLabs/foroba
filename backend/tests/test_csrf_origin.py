"""Pre-beta Task 2.2: unsafe requests from a foreign Origin are refused."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from csrf_origin import OriginCheckMiddleware

_ALLOWED = ["https://app.forobalabs.com", " capacitor://localhost "]


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware, allowed_origins=_ALLOWED)

    @app.post("/x")
    def post_x() -> dict:
        return {"ok": True}

    @app.get("/x")
    def get_x() -> dict:
        return {"ok": True}

    return TestClient(app)


def test_foreign_origin_post_is_refused():
    r = _client().post("/x", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_null_origin_post_is_refused():
    assert _client().post("/x", headers={"Origin": "null"}).status_code == 403


def test_allowed_origins_pass():
    c = _client()
    assert c.post("/x", headers={"Origin": "https://app.forobalabs.com"}).status_code == 200
    assert c.post("/x", headers={"Origin": "capacitor://localhost"}).status_code == 200


def test_no_origin_passes():
    assert _client().post("/x").status_code == 200


def test_safe_method_from_foreign_origin_passes():
    assert _client().get("/x", headers={"Origin": "https://evil.example"}).status_code == 200


def test_main_app_installs_the_check():
    import main

    assert any(m.cls is OriginCheckMiddleware for m in main.app.user_middleware)
