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
        events_by_month[ev["month_offset"]] = events_by_month.get(ev["month_offset"], 0) + ev["amount_cents"]

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
