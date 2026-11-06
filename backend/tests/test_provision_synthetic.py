import sqlite3
import stat

import pytest

from auth import repository as repo
from auth.security import verify_password
from db import init_schema
from scripts import provision_synthetic as ps


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    init_schema(connection)
    return connection


def _user(conn, email):
    return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def test_provision_synthetic_creates_flagged_users(conn, tmp_path, capsys):
    out = tmp_path / "synthetic-users.txt"
    ps.main(["--count", "6", "--prefix", "beta-synth", "--out", str(out)], conn=conn)

    expected = [
        ("base", "free", False),
        ("base", "premium", False),
        ("expert", "free", False),
        ("expert", "premium", False),
        ("base", "premium", True),
        ("base", "free", True),
    ]
    for i, (audience, tier, in_household) in enumerate(expected, start=1):
        row = _user(conn, f"beta-synth-{i}@forobalabs.com")
        assert row is not None
        assert row["is_synthetic"] == 1
        assert (row["audience"], row["tier"]) == (audience, tier)
        assert (row["household_id"] is not None) == in_household
    assert (
        _user(conn, "beta-synth-5@forobalabs.com")["household_id"]
        == _user(conn, "beta-synth-6@forobalabs.com")["household_id"]
    )

    lines = out.read_text().splitlines()
    assert len(lines) == 6
    email, password = lines[0].split("\t")[:2]
    assert email == "beta-synth-1@forobalabs.com"
    assert len(password) >= 20
    assert verify_password(password, _user(conn, email)["password_hash"])
    assert stat.S_IMODE(out.stat().st_mode) == 0o600

    printed = capsys.readouterr()
    for line in lines:
        assert line.split("\t")[1] not in printed.out + printed.err


def test_provision_synthetic_skips_existing_and_refuses_overwrite(conn, tmp_path):
    out = tmp_path / "users.txt"
    ps.main(["--count", "2", "--prefix", "lt", "--out", str(out)], conn=conn)
    with pytest.raises(SystemExit):
        ps.main(["--count", "2", "--prefix", "lt", "--out", str(out)], conn=conn)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2


def test_delete_only_removes_flagged_users_with_prefix(conn, tmp_path):
    ps.main(["--count", "3", "--prefix", "lt", "--out", str(tmp_path / "a.txt")], conn=conn)
    ps.main(["--count", "1", "--prefix", "keep", "--out", str(tmp_path / "b.txt")], conn=conn)
    # A real user whose address happens to match the prefix must survive.
    repo.create_user(conn, email="lt-9@forobalabs.com", name="Real", password_hash="x")

    ps.main(["--delete", "--prefix", "lt"], conn=conn)

    emails = {r["email"] for r in conn.execute("SELECT email FROM users")}
    assert emails == {"keep-1@forobalabs.com", "lt-9@forobalabs.com"}


def test_admin_metrics_exclude_synthetic(conn, tmp_path):
    repo.create_user(conn, email="real@example.com", name="Real", password_hash="x")
    ps.main(["--count", "4", "--prefix", "lt", "--out", str(tmp_path / "u.txt")], conn=conn)

    kpis = repo.get_admin_kpis(conn)

    assert kpis["total_users"] == 1
    assert kpis["users_by_tier"] == {"free": 1}
    assert kpis["users_by_audience"] == {"base": 1}
    assert kpis["signups_last_7d"] == 1
    assert kpis["signups_last_30d"] == 1
