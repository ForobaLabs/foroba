"""Breach runbook 2.3: MAINTENANCE_MODE=true blocks sign-in, keeps health and reads."""

import pytest
from fastapi.testclient import TestClient

import main
from config import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "maintenance_mode", True)
    return TestClient(main.app)


@pytest.mark.parametrize(
    "path", ["/auth/token", "/auth/login", "/auth/token/refresh", "/auth/register"]
)
def test_sign_in_blocked(client, path):
    r = client.post(path, json={})
    assert r.status_code == 503
    assert "maintenance" in r.json()["detail"].lower()


def test_prefixed_path_blocked(client):
    assert client.post("/api/v1/foroba/auth/token", json={}).status_code == 503


def test_health_still_served(client):
    assert client.get("/health").status_code == 200


def test_off_by_default():
    from config import Settings

    assert Settings().maintenance_mode is False
