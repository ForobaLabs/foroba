from datetime import UTC, datetime

import pytest

import db
import quota
import usage
from auth import Caller

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
FREE = Caller(user_id=7, tier="free", is_admin=False)
PREMIUM = Caller(user_id=8, tier="premium", is_admin=False)


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(usage, "now", lambda: NOW)
    monkeypatch.setenv("AI_TEST_ALLOWLIST", "")


def _seed(conn, caller, neurons, at=None):
    usage.record(
        conn, caller, "pazuru", "chat", "chat", "cloudflare", "m", neurons, 10, "ok",
        at=at or "2026-10-05T10:00:00+00:00",
    )


def test_free_user_over_allowance_gets_plan_quota_exhausted():
    conn = db.connect()
    _seed(conn, FREE, 20000)
    assert quota.check(conn, FREE, "cloud") == "plan_quota_exhausted"


def test_premium_under_allowance_routes_remote():
    conn = db.connect()
    _seed(conn, PREMIUM, 25000)
    assert quota.check(conn, PREMIUM, "cloud") is None


def test_allowlisted_user_unlimited(monkeypatch):
    monkeypatch.setenv("AI_TEST_ALLOWLIST", "7")
    conn = db.connect()
    _seed(conn, FREE, 400000)
    assert quota.check(conn, FREE, "cloud") is None


def test_suite_ceiling_gives_cloud_unavailable(monkeypatch):
    monkeypatch.setenv("CF_AI_MONTHLY_NEURONS", "1000")
    conn = db.connect()
    _seed(conn, Caller(99, "premium", False), 1000)
    assert quota.check(conn, PREMIUM, "cloud") == "cloud_unavailable"


def test_daily_soft_ceiling_gives_cloud_unavailable(monkeypatch):
    monkeypatch.setenv("CF_AI_DAILY_SOFT_NEURONS", "500")
    conn = db.connect()
    _seed(conn, Caller(99, "premium", False), 500, at="2026-10-15T08:00:00+00:00")
    assert quota.check(conn, PREMIUM, "cloud") == "cloud_unavailable"


def test_byok_ignores_allowance_and_suite_ceiling(monkeypatch):
    monkeypatch.setenv("CF_AI_MONTHLY_NEURONS", "10")
    conn = db.connect()
    _seed(conn, FREE, 20000)
    assert quota.check(conn, FREE, "byok") is None


def test_rate_limit_11th_request_in_minute():
    conn = db.connect()
    results = [quota.check(conn, PREMIUM, "byok") for _ in range(11)]
    assert results[:10] == [None] * 10
    assert results[10] == "cloud_unavailable"
    assert quota.check(conn, Caller(9, "free", False), "byok") is None


def test_breaker_blocks_cloud_until_midnight_utc_then_reopens(monkeypatch):
    conn = db.connect()
    until = quota.next_midnight(NOW)
    assert until == datetime(2026, 10, 16, 0, 0, tzinfo=UTC)
    quota.trip_breaker(until, conn)
    assert quota.check(conn, PREMIUM, "cloud") == "cloud_unavailable"
    monkeypatch.setattr(usage, "now", lambda: datetime(2026, 10, 16, 0, 1, tzinfo=UTC))
    assert quota.check(conn, PREMIUM, "cloud") is None


def test_breaker_survives_restart():
    conn = db.connect()
    quota.trip_breaker(quota.next_midnight(NOW), conn)
    quota.reset()
    assert quota.check(conn, PREMIUM, "cloud") is None
    quota.load_breaker(conn)
    assert quota.check(conn, PREMIUM, "cloud") == "cloud_unavailable"
