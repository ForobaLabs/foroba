import sqlite3

import pytest

from settings_store import check_drift, get_all, init_settings, set_value


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_settings(c)
    return c


def test_init_creates_defaults(conn):
    settings = get_all(conn)
    assert settings["premium_gating_enabled"] == "true"
    assert settings["onboarding_mifid_enabled"] == "false"
    assert settings["lab_service_enabled"] == "true"


def test_set_value_updates_key(conn):
    set_value(conn, "premium_gating_enabled", "false")
    settings = get_all(conn)
    assert settings["premium_gating_enabled"] == "false"


def test_init_is_idempotent(conn):
    init_settings(conn)  # call twice
    settings = get_all(conn)
    assert settings["premium_gating_enabled"] == "true"


def test_unknown_key_raises(conn):
    with pytest.raises(ValueError, match="Unknown setting key"):
        set_value(conn, "nonexistent_key", "true")


def test_check_drift_empty_when_at_expected_value(conn):
    assert check_drift(conn) == {}


def test_check_drift_reports_key_when_flipped_away(conn):
    set_value(conn, "premium_gating_enabled", "false")
    assert check_drift(conn) == {"premium_gating_enabled": "false"}
