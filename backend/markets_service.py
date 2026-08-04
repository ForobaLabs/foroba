"""Markets aggregation service — resilient fan-out to Tsumi analysis endpoints.

Foroba's flat-backend style (mirrors jeli_service.py): outward HTTP via httpx
with per-call timeout + try/except so a Tsumi outage degrades gracefully. Each
section that fails becomes None and flips `degraded` to True; the snapshot is
never an error. A1/A3/A4 supply the upstream endpoints:
  - GET {tsumi}/api/markets/combined      -> {consensus: {...}, ...}
  - GET {tsumi}/api/news/sentiment         -> {sentiment, headlines, ...}
  - GET {tsumi}/api/news/headlines         -> {items: [...]}
  - GET {tsumi}/api/screener/scan          -> {results: [...]}

FB-3 (VF sprint): added fetch_overview() for the Markets landing page — top
gainers + top losers (screener top_movers scan, both directions) plus news
headlines for the top gainer, so the page has real content before the user
picks a specific symbol.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from config import settings
from suite_cookies import suite_cookies

logger = logging.getLogger(__name__)

DISCLAIMER = "Informational only — not financial advice."
_TIMEOUT = 4.0
# Screener scan fetches OHLCV for ~10-16 symbols sequentially from Binance/Twelve
# Data/iTick upstream and routinely takes ~7-15s (equity's 16-symbol universe is
# the worst case, measured up to ~14.6s, but upstream rate-limit contention can
# push this higher) — needs a longer budget than the other, single-symbol Tsumi
# endpoints, with generous margin over the measured worst case.
_SCREENER_TIMEOUT = 30.0


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
    cookies: dict[str, str] | None,
    *,
    timeout: float = _TIMEOUT,
) -> Any | None:
    """GET one Tsumi endpoint, returning parsed JSON or None on any failure."""
    try:
        resp = await client.get(url, params=params, cookies=cookies, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("markets snapshot section unavailable (%s): %s", url, exc)
        return None


async def fetch_snapshot(
    symbol: str,
    asset_class: str,
    *,
    cookie: str | None = None,
    stepup_tsumi: str | None = None,
) -> dict[str, Any]:
    """Aggregate Tsumi rating + sentiment + top movers into one snapshot.

    Always returns a dict; failed sections are None and set degraded=True.
    """
    base = settings.tsumi_api_url.rstrip("/")
    common = {"symbol": symbol, "asset_class": asset_class}
    cookies = suite_cookies(cookie, stepup_tsumi=stepup_tsumi)
    async with httpx.AsyncClient() as client:
        combined, sentiment, scan = await asyncio.gather(
            _get_json(client, f"{base}/api/markets/combined", common, cookies),
            _get_json(client, f"{base}/api/news/sentiment", common, cookies),
            _get_json(
                client,
                f"{base}/api/screener/scan",
                {"asset_class": asset_class, "screen": "top_movers", "limit": 5},
                cookies,
                timeout=_SCREENER_TIMEOUT,
            ),
        )

    rating = combined.get("consensus") if isinstance(combined, dict) else None
    movers = scan.get("results") if isinstance(scan, dict) else None
    degraded = rating is None or sentiment is None or movers is None

    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "rating": rating,
        "sentiment": sentiment,
        "movers": movers,
        "degraded": degraded,
        "disclaimer": DISCLAIMER,
    }


async def fetch_overview(
    asset_class: str, *, cookie: str | None = None, stepup_tsumi: str | None = None
) -> dict[str, Any]:
    """Aggregate top gainers, top losers, and news headlines for the Markets landing page.

    News is fetched for the top gainer's symbol (best-effort — there is no
    symbol-agnostic "general market" feed upstream); empty if no movers.
    """
    base = settings.tsumi_api_url.rstrip("/")
    cookies = suite_cookies(cookie, stepup_tsumi=stepup_tsumi)
    async with httpx.AsyncClient() as client:
        # Single-fetch-pass movers endpoint: fetches the universe ONCE and
        # derives both gainers and losers from the same rows, avoiding the
        # double network fetch (and consequent Twelve Data rate-limit
        # failures on equity) that two separate top_movers scans incurred.
        movers = await _get_json(
            client,
            f"{base}/api/screener/movers",
            {"asset_class": asset_class, "limit": 5},
            cookies,
            timeout=_SCREENER_TIMEOUT,
        )
        gainers = movers.get("gainers") if isinstance(movers, dict) else None
        losers = movers.get("losers") if isinstance(movers, dict) else None

        news = None
        if gainers:
            top_symbol = gainers[0].get("symbol")
            if top_symbol:
                news = await _get_json(
                    client,
                    f"{base}/api/news/headlines",
                    {"symbol": top_symbol, "limit": 10},
                    cookies,
                )

    degraded = gainers is None or losers is None or news is None

    return {
        "asset_class": asset_class,
        "gainers": gainers,
        "losers": losers,
        "news": news,
        "degraded": degraded,
        "disclaimer": DISCLAIMER,
    }
