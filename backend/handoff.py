"""Same-origin session handoff codes (Plan U, pazuru#150 — DuckDNS PSL cross-domain
cookie scoping; reworked in Plan AK for foroba#300 / AI-6-F1, F3).

`suite_session`/`stepup_<app>` are set by Foroba's backend and never reach
Pazuru/Tsumi's origins, since every `*.duckdns.org` subdomain is its own
registrable domain per the Public Suffix List. The browser is therefore redirected to
the target app with an **opaque one-time code** (no session material in the URL, so
nothing replayable lands in history, access logs or `Referer`). The target app redeems
the code server-to-server against Foroba (`POST /internal/handoff/redeem`, shared
X-Internal-Token), receives the session/step-up cookie values, and Set-Cookies them
onto its own origin.

The store lives in this process (single uvicorn worker, same assumption as the session
revocation floor): codes are 30 s, single-use, bounded, and lost on restart.
"""

from __future__ import annotations

import secrets
import threading
import time

_HANDOFF_TTL_SECONDS = 30
_MAX_CODES = 10_000
VALID_APPS = {"pazuru", "tsumi"}

_codes: dict[str, dict] = {}
_lock = threading.Lock()


class HandoffTokenError(Exception):
    """Raised for any invalid/expired/mismatched/already-used handoff code."""


def _purge_expired(now: float) -> None:
    for key in [k for k, v in _codes.items() if v["exp"] <= now]:
        del _codes[key]


def issue_handoff_code(
    *, user_id: int, app: str, redirect: str, sess: str, stepup: str | None
) -> str:
    if app not in VALID_APPS:
        raise ValueError(f"unknown handoff target app {app!r}")
    code = secrets.token_urlsafe(32)
    now = time.time()
    with _lock:
        _purge_expired(now)
        while len(_codes) >= _MAX_CODES:  # drop the oldest rather than grow unbounded
            del _codes[min(_codes, key=lambda k: _codes[k]["exp"])]
        _codes[code] = {
            "user_id": user_id,
            "app": app,
            "redirect": redirect,
            "sess": sess,
            "stepup": stepup,
            "exp": now + _HANDOFF_TTL_SECONDS,
        }
    return code


def redeem_handoff_code(code: str, *, expected_app: str) -> dict:
    """Atomically consume `code`; any failure leaves no reusable entry behind."""
    with _lock:
        entry = _codes.pop(code, None)
    if entry is None:
        raise HandoffTokenError("Unknown or already used handoff code")
    if entry["exp"] <= time.time():
        raise HandoffTokenError("Handoff code expired")
    if entry["app"] != expected_app:
        raise HandoffTokenError(
            f"Code is scoped to app={entry['app']!r}, expected {expected_app!r}"
        )
    return {
        "sess": entry["sess"],
        "stepup": entry["stepup"],
        "redirect": entry["redirect"],
        "user_id": entry["user_id"],
    }
