"""Markets aggregation service — resilient fan-out to Tsumi analysis endpoints.

Foroba's flat-backend style (mirrors jeli_service.py): outward HTTP via httpx
with per-call timeout + try/except so a Tsumi outage degrades gracefully. Each
section that fails becomes None and flips `degraded` to True; the snapshot is
never an error. A1/A3/A4 supply the upstream endpoints:
  - GET {tsumi}/api/markets/combined      -> {rating: {...}, ...}
  - GET {tsumi}/api/news/sentiment         -> {sentiment, headlines, ...}
  - GET {tsumi}/api/screener/scan          -> {results: [...]}
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)

DISCLAIMER = "Informational only — not financial advice."
_TIMEOUT = 4.0


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
    cookie: str | None,
) -> Any | None:
    """GET one Tsumi endpoint, returning parsed JSON or None on any failure."""
    cookies = {"suite_session": cookie} if cookie else None
    try:
        resp = await client.get(url, params=params, cookies=cookies, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001 — system boundary: Tsumi may be offline
        logger.warning("markets snapshot section unavailable (%s): %s", url, exc)
        return None


async def fetch_snapshot(
    symbol: str,
    asset_class: str,
    *,
    cookie: str | None = None,
) -> dict[str, Any]:
    """Aggregate Tsumi rating + sentiment + top movers into one snapshot.

    Always returns a dict; failed sections are None and set degraded=True.
    """
    base = settings.tsumi_api_url.rstrip("/")
    common = {"symbol": symbol, "asset_class": asset_class}
    async with httpx.AsyncClient() as client:
        combined, sentiment, scan = await asyncio.gather(
            _get_json(client, f"{base}/api/markets/combined", common, cookie),
            _get_json(client, f"{base}/api/news/sentiment", common, cookie),
            _get_json(
                client,
                f"{base}/api/screener/scan",
                {"asset_class": asset_class, "screen": "top_movers", "limit": 5},
                cookie,
            ),
        )

    rating = combined.get("rating") if isinstance(combined, dict) else None
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
