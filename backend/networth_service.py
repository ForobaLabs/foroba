"""Net worth aggregation service — resilient fan-out to Pazuru + Tsumi (foroba#157,
extended in TI-D item 3 Plan 3, foroba#164 for manual-asset folding + FX-ready totals).

Mirrors markets_service.py's flat-backend style: outward HTTP via httpx with
per-call timeout + try/except so a Pazuru or Tsumi outage degrades gracefully.
Each section that fails becomes None and flips `degraded` to True; the payload
is never an error.

Upstream endpoints:
  - GET {pazuru}/api/accounts/net-worth?days=N -> {summary: {...}, history: [...]}
    (bank accounts, converted to EUR by Pazuru's own fx_service, pazuru#99)
  - GET {tsumi}/api/portfolio/summary          -> {total_eur, manual_assets_eur,
    pnl_eur, pnl_pct, position_count} (manual_assets_eur added tsumi#177 and
    already folded into total_eur — see portfolio_service.py: total_eur =
    positions_total_eur + manual_assets_eur — so it must NOT be added again here)
  - GET {tsumi}/api/portfolio/history?days=N   -> [{date, value}] (sparse, ETF only)
  - GET {tsumi}/api/manual-assets/net-worth-history?days=N -> [{date, value_eur}]
    (dense daily, forward-filled by Tsumi — only fetched when include_manual_assets=True,
    used purely to break `investments_eur` vs `manual_assets_eur` apart per-day for the
    history chart; never added a second time into the aggregate total)

All figures are in EUR. Display-currency conversion happens client-side (see
fx_service.py + CurrencyContext.tsx) — this service never converts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from config import settings
from suite_cookies import suite_cookies

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Bank + investment totals in EUR. Amounts are converted to your display "
    "currency for viewing only."
)
_TIMEOUT = 4.0


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
    cookies: dict[str, str] | None,
) -> Any | None:
    """GET one upstream endpoint, returning parsed JSON or None on any failure."""
    try:
        resp = await client.get(url, params=params, cookies=cookies, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("net worth section unavailable (%s): %s", url, exc)
        return None


_MAX_EVENTS = 12


def _import_events(entries: Any) -> list[dict[str, str]]:
    """Map Pazuru's import log to chart annotations (ID-06).

    Keeps non-undone account imports that actually added rows, newest 12 only.
    Labels are the file name — never amounts or counts.
    """
    if not isinstance(entries, list):
        return []
    events: list[dict[str, str]] = []
    for e in entries:
        if not isinstance(e, dict) or e.get("undone") or not e.get("imported_count"):
            continue
        if e.get("destination") not in (None, "account"):
            continue
        created = str(e.get("created_at") or "")[:10]
        if len(created) != 10:
            continue
        label = str(e.get("filename") or "")[:60]
        events.append({"date": created, "label": label, "kind": "import"})
    events.sort(key=lambda ev: ev["date"], reverse=True)
    return sorted(events[:_MAX_EVENTS], key=lambda ev: ev["date"])


async def _fetch_import_events(
    client: httpx.AsyncClient, base: str, cookies: dict[str, str] | None
) -> list[dict[str, str]]:
    """Best-effort: a 428/outage/anything else yields [] and never marks the payload degraded."""
    try:
        return _import_events(await _get_json(client, f"{base}/api/import/log", {}, cookies))
    except Exception:
        return []


def _merge_history(
    bank_history: list[dict[str, Any]],
    investments_history: list[dict[str, Any]],
    manual_assets_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Combine bank (dense, daily) + investments (sparse, trading-day) +
    manual assets (dense daily, already forward-filled by Tsumi) series.

    Anchors on the bank history's date range (already dense — one point per
    calendar day, see Pazuru's net_worth_history) and forward-fills the
    investments value onto it, same pattern as Pazuru's own per-account
    forward-fill. Manual assets history is looked up by exact date (Tsumi
    already forward-fills every calendar day in its own response), defaulting
    to 0 for dates outside its range. Dates before the first investments data
    point default to 0.
    """
    inv_by_date = {p["date"]: p["value"] for p in investments_history}
    inv_dates = sorted(inv_by_date)
    manual_by_date = {p["date"]: p["value_eur"] for p in manual_assets_history}

    result: list[dict[str, Any]] = []
    inv_running = 0.0
    idx = 0
    for point in bank_history:
        d = point["date"]
        while idx < len(inv_dates) and inv_dates[idx] <= d:
            inv_running = inv_by_date[inv_dates[idx]]
            idx += 1
        bank_eur = round(point["balance_cents"] / 100, 2)
        manual_eur = round(manual_by_date.get(d, 0.0), 2)
        result.append(
            {
                "date": d,
                "bank_eur": bank_eur,
                "investments_eur": round(inv_running, 2),
                "manual_assets_eur": manual_eur,
                "total_eur": round(bank_eur + inv_running + manual_eur, 2),
            }
        )
    return result


async def fetch_networth(
    days: int = 365,
    *,
    cookie: str | None = None,
    stepup_pazuru: str | None = None,
    stepup_tsumi: str | None = None,
    include_manual_assets: bool = True,
    include_debts: bool = False,
) -> dict[str, Any]:
    """Aggregate Pazuru bank net worth + Tsumi portfolio value (already including
    manual assets, tsumi#177) + (optionally) Tsumi's manual-asset daily history
    + (optionally) Pazuru's manual-debt total (pazuru#99, TI-D item 3 Plan 1
    debts module) into one view.

    Always returns a dict; failed sections are None and set degraded=True.
    """
    pazuru_base = settings.pazuru_api_url.rstrip("/")
    tsumi_base = settings.tsumi_api_url.rstrip("/")
    cookies = suite_cookies(cookie, stepup_pazuru=stepup_pazuru, stepup_tsumi=stepup_tsumi)

    async with httpx.AsyncClient() as client:
        fetches = [
            _get_json(client, f"{pazuru_base}/api/accounts/net-worth", {"days": days}, cookies),
            _get_json(client, f"{tsumi_base}/api/portfolio/summary", {}, cookies),
            _get_json(client, f"{tsumi_base}/api/portfolio/history", {"days": days}, cookies),
        ]
        if include_manual_assets:
            fetches.append(
                _get_json(
                    client,
                    f"{tsumi_base}/api/manual-assets/net-worth-history",
                    {"days": days},
                    cookies,
                )
            )
        if include_debts:
            fetches.append(_get_json(client, f"{pazuru_base}/api/debts/net-worth", {}, cookies))
        fetches.append(_fetch_import_events(client, pazuru_base, cookies))
        results = await asyncio.gather(*fetches)
    events = results.pop()

    bank, investments_summary, investments_history = results[0], results[1], results[2]
    idx = 3
    manual_assets_history = results[idx] if include_manual_assets else []
    if include_manual_assets:
        idx += 1
    debts_summary = results[idx] if include_debts else None

    bank_summary = bank.get("summary") if isinstance(bank, dict) else None
    bank_history = bank.get("history") if isinstance(bank, dict) else None
    degraded = bank_summary is None or investments_summary is None or investments_history is None

    bank_total_eur = round(bank_summary["total_cents"] / 100, 2) if bank_summary else 0.0
    # Tsumi's total_eur already includes manual_assets_eur (tsumi#177,
    # portfolio_service.py) — do not add it again here.
    investments_total_eur = investments_summary["total_eur"] if investments_summary else 0.0
    total_eur = round(bank_total_eur + investments_total_eur, 2)

    result: dict[str, Any] = {
        "bank": bank_summary,
        "investments": investments_summary,
        "total_eur": total_eur,
        "history": _merge_history(
            bank_history or [], investments_history or [], manual_assets_history or []
        ),
        "events": events,
        "degraded": degraded,
        "disclaimer": DISCLAIMER,
    }
    if include_debts and debts_summary is not None:
        debts_eur = round(debts_summary["total_debt_cents"] / 100, 2)
        result["debts_eur"] = debts_eur
        result["total_eur"] = round(total_eur - debts_eur, 2)
    return result
