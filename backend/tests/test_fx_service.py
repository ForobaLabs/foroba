"""Tests for fx_service.py — TI-D item 3 Plan 3, foroba#164. All HTTP calls to
Frankfurter are mocked via respx; no real network access."""
from __future__ import annotations

import sqlite3
from datetime import date

import httpx
import pytest
import respx

import db
import fx_service

FRANKFURTER_LATEST_URL = "https://api.frankfurter.app/latest"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_schema(c)
    return c


def test_get_rate_eur_returns_one_without_network_call(conn):
    with respx.mock(assert_all_called=False) as mock:
        rate = fx_service.get_rate(conn, "EUR")
        assert rate == 1.0
        assert mock.calls.call_count == 0


@respx.mock
def test_get_rate_fetches_and_caches_on_miss(conn):
    respx.get(FRANKFURTER_LATEST_URL).mock(
        return_value=httpx.Response(
            200,
            json={"amount": 1, "base": "EUR", "date": "2026-07-22", "rates": {"USD": 1.08}},
        )
    )
    rate = fx_service.get_rate(conn, "USD")
    assert round(rate, 6) == round(1 / 1.08, 6)

    cached = conn.execute("SELECT rate_to_eur FROM fx_rates WHERE currency = 'USD'").fetchone()
    assert cached is not None
    assert round(cached[0], 6) == round(1 / 1.08, 6)


def test_get_rate_returns_cached_value_without_network_call(conn):
    conn.execute(
        "INSERT INTO fx_rates (currency, rate_to_eur, rate_date) VALUES (?, ?, ?)",
        ("GBP", 1.15, date.today().isoformat()),
    )
    conn.commit()
    with respx.mock(assert_all_called=False) as mock:
        rate = fx_service.get_rate(conn, "GBP")
        assert rate == 1.15
        assert mock.calls.call_count == 0


@respx.mock
def test_get_rate_falls_back_to_stale_cache_on_network_failure(conn):
    respx.get(FRANKFURTER_LATEST_URL).mock(return_value=httpx.Response(500))
    conn.execute(
        "INSERT INTO fx_rates (currency, rate_to_eur, rate_date) VALUES (?, ?, ?)",
        ("JPY", 0.0061, date(2026, 1, 1).isoformat()),
    )
    conn.commit()
    rate = fx_service.get_rate(conn, "JPY")
    assert rate == 0.0061


@respx.mock
def test_get_rate_raises_when_no_cache_and_network_fails(conn):
    respx.get(FRANKFURTER_LATEST_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(fx_service.FxRateUnavailable):
        fx_service.get_rate(conn, "CHF")


@respx.mock
def test_convert_amount_between_currencies(conn):
    respx.get(FRANKFURTER_LATEST_URL).mock(
        return_value=httpx.Response(
            200,
            json={"amount": 1, "base": "EUR", "date": "2026-07-22", "rates": {"USD": 1.08}},
        )
    )
    eur_amount = fx_service.convert(conn, 108.0, "USD")
    assert round(eur_amount, 2) == 100.0


@respx.mock
def test_refresh_latest_rates_upserts_multiple_currencies(conn):
    respx.get(FRANKFURTER_LATEST_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "amount": 1, "base": "EUR", "date": "2026-07-22",
                "rates": {"USD": 1.08, "GBP": 0.86},
            },
        )
    )
    fx_service.refresh_latest_rates(conn)

    rows = conn.execute("SELECT DISTINCT currency FROM fx_rates").fetchall()
    assert {r[0] for r in rows} == {"USD", "GBP"}


@respx.mock
def test_refresh_latest_rates_swallows_network_failure(conn):
    respx.get(FRANKFURTER_LATEST_URL).mock(return_value=httpx.Response(500))
    fx_service.refresh_latest_rates(conn)  # must not raise
    assert conn.execute("SELECT COUNT(*) FROM fx_rates").fetchone()[0] == 0
