"""FX conversion service — cache-first EUR conversion via Frankfurter (ECB),
TI-D item 3 Plan 3, foroba#164.

Same shape and resilience philosophy as Pazuru's services/fx_service.py and
Tsumi's services/fx_service.py: cache-first on (currency, rate_date), fall back
to the most recent cached rate on Frankfurter failure, raise FxRateUnavailable
only when there is truly no cache at all.

IMPORTANT: api.frankfurter.app 301-redirects to api.frankfurter.dev (discovered
live during Plan 1 / pazuru#99) — httpx does not follow redirects by default,
so follow_redirects=True is required on every request.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date

import httpx

logger = logging.getLogger(__name__)

FRANKFURTER_BASE_URL = "https://api.frankfurter.app"
_TIMEOUT = 5.0


class FxRateUnavailable(Exception):
    """Raised when no rate (cached or live) can be found for a currency."""


def _fetch_rates(rate_date: date | None) -> dict[str, float]:
    """Fetch EUR-based rates from Frankfurter for `rate_date` (or latest if None).

    Returns a dict like {"USD": 1.08, ...} meaning "1 EUR = 1.08 USD".
    """
    path = "/latest" if rate_date is None else f"/{rate_date.isoformat()}"
    resp = httpx.get(
        f"{FRANKFURTER_BASE_URL}{path}",
        params={"base": "EUR"},
        timeout=_TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.json()["rates"]


def _upsert_rate(
    conn: sqlite3.Connection, currency: str, rate_to_eur: float, rate_date: date
) -> None:
    conn.execute(
        """
        INSERT INTO fx_rates (currency, rate_to_eur, rate_date, fetched_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(currency, rate_date)
        DO UPDATE SET rate_to_eur = excluded.rate_to_eur, fetched_at = excluded.fetched_at
        """,
        (currency, rate_to_eur, rate_date.isoformat()),
    )
    conn.commit()


def refresh_latest_rates(conn: sqlite3.Connection) -> None:
    """Fetch today's rates from Frankfurter and upsert into fx_rates.

    Called by the daily scheduler job (fx_scheduler.py). Any failure is logged
    and swallowed — the next scheduled run, or an on-demand get_rate() call,
    will retry. Never raises.
    """
    try:
        rates = _fetch_rates(None)
    except Exception as exc:
        logger.warning("FX rate refresh failed: %s", exc)
        return

    today = date.today()
    for currency, eur_per_unit in rates.items():
        _upsert_rate(conn, currency, 1 / eur_per_unit, today)
    logger.info("Refreshed %d FX rates for %s.", len(rates), today.isoformat())


def get_rate(
    conn: sqlite3.Connection, currency: str, rate_date: date | None = None
) -> float:
    """Return how many EUR 1 unit of `currency` is worth on `rate_date` (default: today).

    Cache-first: looks up the exact (currency, rate_date) row. On miss, fetches
    that date from Frankfurter (or "latest" when rate_date is None) and caches
    it. If Frankfurter is unreachable, falls back to the most recent cached
    rate for that currency (any date). Raises FxRateUnavailable only if there
    is no cached rate at all and Frankfurter cannot be reached.
    """
    if currency == "EUR":
        return 1.0

    lookup_date = rate_date or date.today()
    row = conn.execute(
        "SELECT rate_to_eur FROM fx_rates WHERE currency = ? AND rate_date = ?",
        (currency, lookup_date.isoformat()),
    ).fetchone()
    if row:
        return row[0]

    try:
        rates = _fetch_rates(rate_date)
    except Exception as exc:
        logger.warning("FX rate fetch failed for %s on %s: %s", currency, lookup_date, exc)
        fallback = conn.execute(
            "SELECT rate_to_eur FROM fx_rates WHERE currency = ? ORDER BY rate_date DESC LIMIT 1",
            (currency,),
        ).fetchone()
        if fallback:
            return fallback[0]
        raise FxRateUnavailable(
            f"No cached or live FX rate available for {currency!r}"
        ) from exc

    if currency not in rates:
        raise FxRateUnavailable(f"Frankfurter has no rate for currency {currency!r}")

    rate_to_eur = 1 / rates[currency]
    _upsert_rate(conn, currency, rate_to_eur, lookup_date)
    return rate_to_eur


def convert(
    conn: sqlite3.Connection,
    amount: float,
    from_currency: str,
    to_currency: str = "EUR",
    rate_date: date | None = None,
) -> float:
    """Convert `amount` in `from_currency` to `to_currency` (default EUR)."""
    if from_currency == to_currency:
        return amount
    eur_amount = amount * get_rate(conn, from_currency, rate_date)
    if to_currency == "EUR":
        return eur_amount
    return eur_amount / get_rate(conn, to_currency, rate_date)
