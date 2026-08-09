"""CL-2.4 — structured security audit log + repeated-failure alerting (foroba#241).

Covers GDPR art.32 technical measures + NIS2 incident detection baseline.
Events are written synchronously so they're never silently dropped.
Alerting is best-effort: if sentry_sdk is unavailable the log entry still persists.
"""

from __future__ import annotations

import logging

import sentry_sdk

logger = logging.getLogger(__name__)

_ALERT_EVENTS = {"login_failed", "mfa_failed"}
_ALERT_THRESHOLD = 5
_ALERT_WINDOW_MINUTES = 15


def _alert(message: str) -> None:
    """Send an alert to GlitchTip/Sentry."""
    sentry_sdk.capture_message(message, level="warning")


def log_event(
    conn,
    *,
    user_id: int | None,
    event: str,
    detail: str | None,
    ip: str | None,
) -> None:
    """Persist a security event and trigger an alert if a threshold is exceeded."""
    conn.execute(
        "INSERT INTO security_events (user_id, event, detail, ip) VALUES (?,?,?,?)",
        (user_id, event, detail, ip),
    )
    conn.commit()
    if event in _ALERT_EVENTS and ip:
        n = conn.execute(
            "SELECT count(*) FROM security_events WHERE event=? AND ip=? "
            "AND created_at > datetime('now', ?)",
            (event, ip, f"-{_ALERT_WINDOW_MINUTES} minutes"),
        ).fetchone()[0]
        if n >= _ALERT_THRESHOLD:
            try:
                _alert(f"{n}x {event} from {ip} in {_ALERT_WINDOW_MINUTES}min")
            except Exception:
                logger.warning("sentry alert failed", exc_info=True)


def recent_events(conn, limit: int = 100) -> list[dict]:
    """Return the most recent security events (newest first)."""
    cur = conn.execute(
        "SELECT user_id, event, detail, ip, created_at FROM security_events "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
