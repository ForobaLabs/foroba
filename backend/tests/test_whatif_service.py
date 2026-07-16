"""Tests for the pure what-if projection engine (foroba#162)."""
from __future__ import annotations

import whatif_service as ws


def test_projection_monthly_resolution_for_first_24_months():
    points = ws.compute_projection(
        horizon_months=24, bank_total_cents=100_000, investments_total_eur=0.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[], investment_growth_rate_pct=0.0,
    )
    assert len(points) == 24
    assert all(p["resolution"] == "monthly" for p in points)
    assert [p["month"] for p in points] == list(range(1, 25))


def test_projection_quarterly_resolution_between_25_and_60():
    points = ws.compute_projection(
        horizon_months=60, bank_total_cents=0, investments_total_eur=0.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[], investment_growth_rate_pct=0.0,
    )
    quarterly = [p for p in points if p["resolution"] == "quarterly"]
    assert [p["month"] for p in quarterly] == [27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57, 60]


def test_projection_yearly_resolution_beyond_60_and_includes_final_month():
    points = ws.compute_projection(
        horizon_months=100, bank_total_cents=0, investments_total_eur=0.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[], investment_growth_rate_pct=0.0,
    )
    yearly = [p for p in points if p["resolution"] == "yearly"]
    assert yearly[-1]["month"] == 100  # final partial year still emitted
    assert [p["month"] for p in yearly[:-1]] == [72, 84, 96]


def test_projection_applies_monthly_net_delta_and_savings_and_income():
    points = ws.compute_projection(
        horizon_months=1, bank_total_cents=100_000, investments_total_eur=0.0,
        monthly_net_delta_cents=10_000, spend_cut_savings_cents=5_000,
        income_delta_cents=2_000, one_off_events=[], investment_growth_rate_pct=0.0,
    )
    # 100000 + 10000 + 5000 + 2000 = 117000 cents = 1170.00 EUR
    assert points[0]["bank_eur"] == 1170.0


def test_projection_applies_one_off_event_at_correct_month():
    points = ws.compute_projection(
        horizon_months=3, bank_total_cents=0, investments_total_eur=0.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[{"month_offset": 2, "amount_cents": 50_000, "label": "Bonus"}],
        investment_growth_rate_pct=0.0,
    )
    assert points[0]["bank_eur"] == 0.0
    assert points[1]["bank_eur"] == 500.0
    assert points[2]["bank_eur"] == 500.0  # persists forward


def test_projection_compounds_investments_monthly():
    points = ws.compute_projection(
        horizon_months=12, bank_total_cents=0, investments_total_eur=1000.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[], investment_growth_rate_pct=12.0,  # 1%/month
    )
    # 1000 * 1.01^12 ≈ 1126.83
    assert abs(points[-1]["investments_eur"] - 1126.83) < 0.5
