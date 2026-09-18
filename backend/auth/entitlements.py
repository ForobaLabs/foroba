"""Feature registry and access evaluation (two orthogonal axes).

audience: base < expert  (UI complexity / progressive disclosure)
tier:     free  < premium (monetization)

A feature is *visible* when the user's audience >= the feature's audience,
and *unlocked* when the user's tier >= the feature's tier. When gating is
disabled (dev/demo) everything is visible and unlocked.
"""

from __future__ import annotations

from dataclasses import dataclass

_AUDIENCE_RANK = {"base": 0, "expert": 1}
_TIER_RANK = {"free": 0, "premium": 1}

# Single source of truth (mirrored in @foroba/ui registry.ts). See decision D6.
REGISTRY: dict[str, dict[str, str]] = {
    "markets.summary_rating": {"audience": "base", "tier": "free"},
    "markets.top_movers_basic": {"audience": "base", "tier": "free"},
    "markets.news_headlines": {"audience": "base", "tier": "free"},
    "markets.indicators_raw": {"audience": "expert", "tier": "premium"},
    "markets.multi_timeframe": {"audience": "expert", "tier": "premium"},
    "markets.backtesting": {"audience": "expert", "tier": "premium"},
    "markets.compare_strategies": {"audience": "expert", "tier": "premium"},
    "markets.walk_forward": {"audience": "expert", "tier": "premium"},
    "markets.volume_scanners": {"audience": "expert", "tier": "premium"},
    "markets.rating_filter": {"audience": "expert", "tier": "premium"},
    "markets.sentiment": {"audience": "base", "tier": "premium"},
    "markets.sentiment_divergence": {"audience": "expert", "tier": "premium"},
    "markets.market_snapshot": {"audience": "base", "tier": "premium"},
    "markets.comparator": {"audience": "expert", "tier": "premium"},
    "markets.simulations": {"audience": "expert", "tier": "premium"},
    "banking.chat": {"audience": "base", "tier": "premium"},
    "banking.ai_insights": {"audience": "base", "tier": "premium"},
    "banking.tax_export": {"audience": "base", "tier": "premium"},
    "banking.recurring_predictions": {"audience": "base", "tier": "premium"},
    "banking.budget_alerts": {"audience": "base", "tier": "premium"},
    "household.whatif_simulator": {"audience": "expert", "tier": "premium"},
    "banking.monthly_ai_report": {"audience": "base", "tier": "premium"},
    "portfolio.manual_assets": {"audience": "base", "tier": "premium"},
    "banking.pdf_statement_import": {"audience": "base", "tier": "premium"},
    "platform.public_api": {"audience": "base", "tier": "premium"},
    "banking.debts_ai_advisor": {"audience": "base", "tier": "premium"},
}


@dataclass(frozen=True)
class FeatureAccess:
    visible: bool
    unlocked: bool


def evaluate(key: str, user: dict, *, gating_enabled: bool) -> FeatureAccess:
    feature = REGISTRY[key]  # raises KeyError on unknown key
    if not gating_enabled:
        return FeatureAccess(visible=True, unlocked=True)
    visible = _AUDIENCE_RANK[user["audience"]] >= _AUDIENCE_RANK[feature["audience"]]
    unlocked = visible and _TIER_RANK[user["tier"]] >= _TIER_RANK[feature["tier"]]
    return FeatureAccess(visible=visible, unlocked=unlocked)
