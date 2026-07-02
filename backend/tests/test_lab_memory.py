import sqlite3

from db import (
    get_sandbox_history,
    get_sandbox_user_context,
    init_schema,
    save_sandbox_turn,
    update_sandbox_user_context,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_save_and_get_sandbox_history():
    conn = _conn()
    save_sandbox_turn(conn, "u1", "s1", "what's my net worth trend?", "It's up 3%.")
    history = get_sandbox_history(conn, "u1", "s1")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_sandbox_user_context_defaults_and_upserts():
    conn = _conn()
    assert get_sandbox_user_context(conn, "u1") == ""
    update_sandbox_user_context(conn, "u1", "Uses both Pazuru and Tsumi actively.")
    assert get_sandbox_user_context(conn, "u1") == "Uses both Pazuru and Tsumi actively."


def test_get_sandbox_history_returns_most_recent_turns_not_oldest():
    conn = _conn()
    for i in range(8):
        save_sandbox_turn(conn, "u1", "s1", f"question-{i}", f"answer-{i}")
    history = get_sandbox_history(conn, "u1", "s1", limit=4)
    contents = [h["content"] for h in history]
    assert "question-6" in contents
    assert "answer-7" in contents
    assert "question-0" not in contents
