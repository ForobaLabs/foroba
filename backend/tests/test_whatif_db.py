"""CRUD + household-visibility tests for whatif_scenarios (foroba#162)."""
from __future__ import annotations

import sqlite3

import pytest

import db


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_schema(c)
    return c


def test_create_and_get_scenario(conn):
    row = db.create_whatif_scenario(
        conn, created_by_user_id=1, household_id=None,
        name="Early retirement", horizon_months=60, params_json="{}",
    )
    assert row["name"] == "Early retirement"
    fetched = db.get_whatif_scenario(conn, row["id"], user_id=1, household_id=None)
    assert fetched is not None
    assert fetched["id"] == row["id"]


def test_get_scenario_denies_other_private_user(conn):
    row = db.create_whatif_scenario(
        conn, created_by_user_id=1, household_id=None,
        name="Private", horizon_months=12, params_json="{}",
    )
    assert db.get_whatif_scenario(conn, row["id"], user_id=2, household_id=None) is None


def test_household_scenario_visible_to_other_member(conn):
    row = db.create_whatif_scenario(
        conn, created_by_user_id=1, household_id="hh-1",
        name="Shared", horizon_months=24, params_json="{}",
    )
    assert db.get_whatif_scenario(conn, row["id"], user_id=2, household_id="hh-1") is not None
    assert db.get_whatif_scenario(conn, row["id"], user_id=3, household_id="hh-2") is None


def test_list_scenarios_ordered_newest_first(conn):
    db.create_whatif_scenario(conn, created_by_user_id=1, household_id=None, name="A", horizon_months=12, params_json="{}")
    db.create_whatif_scenario(conn, created_by_user_id=1, household_id=None, name="B", horizon_months=12, params_json="{}")
    rows = db.list_whatif_scenarios(conn, user_id=1, household_id=None)
    assert [r["name"] for r in rows] == ["B", "A"]


def test_update_scenario(conn):
    row = db.create_whatif_scenario(conn, created_by_user_id=1, household_id=None, name="A", horizon_months=12, params_json="{}")
    updated = db.update_whatif_scenario(
        conn, row["id"], user_id=1, household_id=None,
        name="A renamed", horizon_months=24, params_json='{"x":1}',
    )
    assert updated["name"] == "A renamed"
    assert updated["horizon_months"] == 24


def test_update_scenario_not_found_returns_none(conn):
    assert db.update_whatif_scenario(conn, 999, user_id=1, household_id=None, name="x", horizon_months=1, params_json="{}") is None


def test_delete_scenario(conn):
    row = db.create_whatif_scenario(conn, created_by_user_id=1, household_id=None, name="A", horizon_months=12, params_json="{}")
    assert db.delete_whatif_scenario(conn, row["id"], user_id=1, household_id=None) is True
    assert db.get_whatif_scenario(conn, row["id"], user_id=1, household_id=None) is None


def test_delete_scenario_not_found_returns_false(conn):
    assert db.delete_whatif_scenario(conn, 999, user_id=1, household_id=None) is False
