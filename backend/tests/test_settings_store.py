import sqlite3
import pytest
from settings_store import init_settings, get_all, set_value, DEFAULT_SETTINGS


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_settings(c)
    return c


def test_init_creates_defaults(conn):
    settings = get_all(conn)
    assert settings["premium_gating_enabled"] == "false"
    assert settings["onboarding_mifid_enabled"] == "false"
    assert settings["lab_service_enabled"] == "true"


def test_set_value_updates_key(conn):
    set_value(conn, "premium_gating_enabled", "true")
    settings = get_all(conn)
    assert settings["premium_gating_enabled"] == "true"


def test_init_is_idempotent(conn):
    init_settings(conn)  # call twice
    settings = get_all(conn)
    assert settings["premium_gating_enabled"] == "false"


def test_unknown_key_raises(conn):
    with pytest.raises(ValueError, match="Unknown setting key"):
        set_value(conn, "nonexistent_key", "true")
