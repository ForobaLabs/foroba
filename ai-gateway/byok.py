"""BYOK vault access. Task 6 replaces `load_key` with the real encrypted vault."""


class KeyNotFound(Exception):
    pass


def load_key(conn, user_id: int, provider: str) -> tuple[str, str | None, str]:
    """Return (api_key, account_id, model) or raise KeyNotFound."""
    raise KeyNotFound(provider)


def mark_invalid(conn, user_id: int, provider: str) -> None:
    conn.execute(
        "UPDATE byok_keys SET status='invalid' WHERE user_id=? AND provider=?",
        (user_id, provider),
    )
    conn.commit()
