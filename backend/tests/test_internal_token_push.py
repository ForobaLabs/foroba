"""foroba#299: downstream pushes carry X-Internal-Token and are skipped when it is unset."""

from __future__ import annotations

import httpx
import pytest

import admin_router
from auth import session_invalidation
from config import settings


@pytest.fixture()
def calls(monkeypatch):
    seen: list[dict] = []

    def _post(url, **kw):
        seen.append({"url": url, **kw})

    monkeypatch.setattr(httpx, "post", _post)
    return seen


def test_session_invalidate_push_sends_token(calls, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "right-token", raising=False)
    session_invalidation.invalidate_sessions_downstream(7, 3)
    assert len(calls) == 2
    assert all(c["headers"] == {"X-Internal-Token": "right-token"} for c in calls)
    assert all(c["url"].endswith("/internal/session-invalidate") for c in calls)


def test_settings_cache_push_sends_token(calls, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "right-token", raising=False)
    admin_router._invalidate_downstream_settings_caches()
    assert len(calls) == 2
    assert all(c["headers"] == {"X-Internal-Token": "right-token"} for c in calls)


def test_pushes_skipped_with_warning_when_token_unset(calls, monkeypatch, caplog):
    monkeypatch.setattr(settings, "internal_api_token", "", raising=False)
    with caplog.at_level("WARNING"):
        session_invalidation.invalidate_sessions_downstream(7, 3)
        admin_router._invalidate_downstream_settings_caches()
    assert calls == []
    assert "INTERNAL_API_TOKEN" in caplog.text
