import pytest

from auth.entitlements import REGISTRY, evaluate, FeatureAccess


def test_registry_has_expected_keys():
    assert "markets.backtesting" in REGISTRY
    assert REGISTRY["markets.backtesting"] == {"audience": "expert", "tier": "premium"}
    assert REGISTRY["markets.summary_rating"] == {"audience": "base", "tier": "free"}


@pytest.mark.parametrize("user, key, visible, unlocked", [
    ({"audience": "base", "tier": "free"}, "markets.summary_rating", True, True),
    ({"audience": "base", "tier": "free"}, "markets.backtesting", False, False),
    ({"audience": "expert", "tier": "free"}, "markets.backtesting", True, False),
    ({"audience": "expert", "tier": "premium"}, "markets.backtesting", True, True),
    ({"audience": "base", "tier": "premium"}, "markets.sentiment", True, True),
    ({"audience": "expert", "tier": "premium"}, "markets.comparator", True, True),
    ({"audience": "base", "tier": "free"}, "markets.comparator", False, False),
    ({"audience": "expert", "tier": "premium"}, "markets.simulations", True, True),
    ({"audience": "base", "tier": "free"}, "markets.simulations", False, False),
    ({"audience": "expert", "tier": "premium"}, "household.whatif_simulator", True, True),
    ({"audience": "base", "tier": "free"}, "household.whatif_simulator", False, False),
])
def test_evaluate(user, key, visible, unlocked):
    res = evaluate(key, user, gating_enabled=True)
    assert res == FeatureAccess(visible=visible, unlocked=unlocked)


def test_gating_disabled_unlocks_everything():
    res = evaluate("markets.backtesting", {"audience": "base", "tier": "free"},
                   gating_enabled=False)
    assert res == FeatureAccess(visible=True, unlocked=True)


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        evaluate("nope", {"audience": "base", "tier": "free"}, gating_enabled=True)
