from fastapi.testclient import TestClient

import config
import main


def test_healthz_open_and_startup_creates_db(tmp_path):
    with TestClient(main.app) as c:
        assert c.get("/healthz").json() == {"ok": True}
    assert (tmp_path / "ai_gateway.db").exists()


def test_allowlist_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("AI_TEST_ALLOWLIST", "3, 9,12")
    config.get_settings.cache_clear()
    assert config.get_settings().test_allowlist == {3, 9, 12}
