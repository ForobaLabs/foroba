"""Route test for GET /fx/rates (TI-D item 3 Plan 3, foroba#164)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import fx_router
from main import app


def test_fx_rates_route_returns_base_and_rates(monkeypatch):
    def _fake_refresh(conn) -> None:
        pass

    def _fake_get_all_rates(conn) -> dict[str, float]:
        return {"USD": 1.08, "GBP": 0.86}

    monkeypatch.setattr(fx_router.fx_service, "refresh_latest_rates", _fake_refresh)
    monkeypatch.setattr(fx_router, "_get_latest_rates", _fake_get_all_rates)

    client = TestClient(app)
    resp = client.get("/fx/rates")
    assert resp.status_code == 200
    body = resp.json()
    assert body["base"] == "EUR"
    assert body["rates"] == {"USD": 1.08, "GBP": 0.86}
    assert "date" in body
