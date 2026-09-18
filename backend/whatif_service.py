"""Household what-if net-worth simulator (foroba#162, TI-D item 1).

Fans out to Pazuru's existing GET /api/accounts/net-worth, GET /api/goals,
POST /api/forecasts/what-if, POST /api/goals/project, and Tsumi's existing
GET /api/portfolio/summary — no new endpoints are needed in either app.

Only scenario *parameters* are ever persisted (see db.py::whatif_scenarios);
every read recomputes this projection live against current data, same
philosophy as Pazuru's project_goal().

Simplification stated to the user via `DISCLAIMER`: investment growth
compounds only the *existing* Tsumi capital — new savings from spend cuts,
income delta, and one-off events are modeled as bank balance only, never as
new investment contributions.
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
    "Projection assumes today's spending cuts, income change, and one-off events repeat "
    "or persist exactly as entered every month of the horizon, and that only the current "
    "investment capital compounds (new savings are modeled as bank balance, not invested). "
    "Longer horizons are shown at coarser resolution to reflect lower confidence. Not "
    "financial advice."
)
_TIMEOUT = 4.0


def _resolution_for(month: int) -> str:
    if month <= 24:
        return "monthly"
    if month <= 60:
        return "quarterly"
    return "yearly"


def _should_emit(month: int, horizon_months: int) -> bool:
    if month <= 24:
        return True
    if month <= 60:
        return month % 3 == 0 or month == horizon_months
    return month % 12 == 0 or month == horizon_months


def compute_projection(
    *,
    horizon_months: int,
    bank_total_cents: int,
    investments_total_eur: float,
    monthly_net_delta_cents: int,
    spend_cut_savings_cents: int,
    income_delta_cents: int,
    one_off_events: list[dict[str, Any]],
    investment_growth_rate_pct: float,
) -> list[dict[str, Any]]:
    """Project bank + investment totals for every month 1..horizon_months,
    emitting only the months selected by the monthly/quarterly/yearly
    resolution tiers. The internal loop always runs monthly regardless of
    horizon so one-off events and compounding stay accurate."""
    events_by_month: dict[int, int] = {}
    for ev in one_off_events:
        events_by_month[ev["month_offset"]] = (
            events_by_month.get(ev["month_offset"], 0) + ev["amount_cents"]
        )

    monthly_growth = investment_growth_rate_pct / 100 / 12
    adjusted_monthly_net = monthly_net_delta_cents + spend_cut_savings_cents + income_delta_cents

    bank_cents = bank_total_cents
    investments_eur = investments_total_eur
    points: list[dict[str, Any]] = []

    for month in range(1, horizon_months + 1):
        bank_cents += adjusted_monthly_net + events_by_month.get(month, 0)
        investments_eur *= 1 + monthly_growth
        if _should_emit(month, horizon_months):
            points.append(
                {
                    "month": month,
                    "resolution": _resolution_for(month),
                    "bank_eur": round(bank_cents / 100, 2),
                    "investments_eur": round(investments_eur, 2),
                    "total_eur": round(bank_cents / 100 + investments_eur, 2),
                }
            )
    return points


def _monthly_net_delta_cents(bank_history: list[dict[str, Any]]) -> int:
    """Approximate current monthly net cash flow (real income minus real
    spend) from the last ~30 days of the daily bank balance history, unlike
    the spend-only forecast/what-if figures which don't model income."""
    if len(bank_history) < 31:
        return 0
    return int(bank_history[-1]["balance_cents"] - bank_history[-31]["balance_cents"])


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any] | None,
    cookies: dict[str, str] | None,
) -> Any | None:
    try:
        resp = await client.get(url, params=params or {}, cookies=cookies, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("whatif section unavailable (%s): %s", url, exc)
        return None


async def _post_json(
    client: httpx.AsyncClient,
    url: str,
    body: dict[str, Any],
    cookies: dict[str, str] | None,
) -> Any | None:
    try:
        resp = await client.post(url, json=body, cookies=cookies, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("whatif section unavailable (%s): %s", url, exc)
        return None


async def _goal_impacts(
    client: httpx.AsyncClient,
    pazuru_base: str,
    cookies: dict[str, str] | None,
    goals: list[dict[str, Any]],
    goal_contributions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    extra_by_goal = {gc["goal_id"]: gc["extra_monthly_cents"] for gc in goal_contributions}
    impacts: list[dict[str, Any]] = []
    for g in goals:
        extra = extra_by_goal.get(g["id"])
        if extra is None:
            continue
        projection = await _post_json(
            client,
            f"{pazuru_base}/api/goals/project",
            {
                "target_cents": g["target_cents"],
                "saved_cents": g["saved_cents"],
                "monthly_contribution_cents": g["monthly_contribution_cents"] + extra,
                "deadline": g["deadline"],
            },
            cookies,
        )
        impacts.append(
            {
                "goal_id": g["id"],
                "name": g["name"],
                "original_projected_completion": g["projected_completion"],
                "new_projection": projection,
            }
        )
    return impacts


async def simulate(
    params: dict[str, Any],
    horizon_months: int,
    *,
    owner_cookie: str | None,
    stepup_pazuru: str | None = None,
    stepup_tsumi: str | None = None,
) -> dict[str, Any]:
    """Fetch current household state from Pazuru+Tsumi and compute the
    projection for the given scenario parameters. Always returns a dict —
    failed upstream sections degrade to 0/None with `degraded=True`, never
    a hard error (same policy as networth_service.fetch_networth)."""
    pazuru_base = settings.pazuru_api_url.rstrip("/")
    tsumi_base = settings.tsumi_api_url.rstrip("/")
    cookies = suite_cookies(owner_cookie, stepup_pazuru=stepup_pazuru, stepup_tsumi=stepup_tsumi)
    include_debts = params.get("include_debts", False)

    async with httpx.AsyncClient() as client:
        fetches = [
            _get_json(client, f"{pazuru_base}/api/accounts/net-worth", {"days": 90}, cookies),
            _get_json(client, f"{tsumi_base}/api/portfolio/summary", {}, cookies),
            _get_json(client, f"{pazuru_base}/api/goals", {}, cookies),
            _post_json(client, f"{pazuru_base}/api/forecasts/what-if", {}, cookies),
            _post_json(
                client,
                f"{pazuru_base}/api/forecasts/what-if",
                {
                    "eliminate_categories": params.get("eliminate_categories"),
                    "reduce_merchant_pct": params.get("reduce_merchant_pct"),
                },
                cookies,
            ),
        ]
        if include_debts:
            fetches.append(_get_json(client, f"{pazuru_base}/api/debts/net-worth", {}, cookies))
        results = await asyncio.gather(*fetches)
        net_worth, investments_summary, goals, what_if_baseline, what_if_adjusted = results[:5]
        debts_summary = results[5] if include_debts else None

        bank_summary = net_worth.get("summary") if isinstance(net_worth, dict) else None
        bank_history = net_worth.get("history") if isinstance(net_worth, dict) else None
        degraded = (
            bank_summary is None
            or investments_summary is None
            or goals is None
            or what_if_baseline is None
            or what_if_adjusted is None
        )

        bank_total_cents = bank_summary["total_cents"] if bank_summary else 0
        investments_total_eur = investments_summary["total_eur"] if investments_summary else 0.0
        monthly_net_delta_cents = _monthly_net_delta_cents(bank_history or [])
        spend_cut_savings_cents = (
            what_if_baseline["base_cents"] - what_if_adjusted["base_cents"]
            if what_if_baseline and what_if_adjusted
            else 0
        )

        debts_total_cents = debts_summary["total_debt_cents"] if debts_summary else 0
        if include_debts and debts_summary is not None:
            bank_total_cents -= debts_total_cents

        goal_impacts = await _goal_impacts(
            client, pazuru_base, cookies, goals or [], params.get("goal_contributions") or []
        )

    points = compute_projection(
        horizon_months=horizon_months,
        bank_total_cents=bank_total_cents,
        investments_total_eur=investments_total_eur,
        monthly_net_delta_cents=monthly_net_delta_cents,
        spend_cut_savings_cents=spend_cut_savings_cents,
        income_delta_cents=params.get("income_delta_cents", 0),
        one_off_events=params.get("one_off_events") or [],
        investment_growth_rate_pct=params.get("investment_growth_rate_pct", 5.0),
    )

    result = {
        "points": points,
        "goal_impacts": goal_impacts,
        "degraded": degraded,
        "disclaimer": DISCLAIMER,
    }
    if include_debts and debts_summary is not None:
        result["debts_eur"] = round(debts_total_cents / 100, 2)
    return result
