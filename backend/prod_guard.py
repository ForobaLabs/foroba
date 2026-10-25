"""Refuse to boot a production container with dev-only settings (Plan AU M-7).

Identical copies live in foroba/backend/prod_guard.py, pazuru/backend/app/prod_guard.py
and tsumi/api/prod_guard.py. A no-op unless ENVIRONMENT=production.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

# pfh-mobile WebView origins (iOS Capacitor/Ionic schemes) are not https:// but are
# not attacker-hostable either; same for the loopback origin Android WebViews use.
_NATIVE_ORIGINS = {"capacitor://localhost", "ionic://localhost"}
_LOOPBACK_RE = re.compile(r"^http://localhost(:\d+)?$")


def _origin_ok(origin: str) -> bool:
    return (
        origin.startswith("https://")
        or origin in _NATIVE_ORIGINS
        or bool(_LOOPBACK_RE.match(origin))
    )


def check_production_config(env: Mapping[str, str], *, cookie_secure: bool | None = None) -> None:
    if env.get("ENVIRONMENT", "").lower() != "production":
        return
    problems: list[str] = []
    if env.get("AUTH_DEV_BYPASS", "false").lower() == "true":
        problems.append("AUTH_DEV_BYPASS=true")
    if len(env.get("INTERNAL_API_TOKEN", "")) < 32:
        problems.append("INTERNAL_API_TOKEN missing or shorter than 32 chars")
    origins = [o.strip() for o in env.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if not origins or any(not _origin_ok(o) for o in origins):
        problems.append("ALLOWED_ORIGINS must be explicit https:// (or native/loopback) origins")
    if cookie_secure is False:
        problems.append("cookie_secure must be true")
    if problems:
        raise RuntimeError("Unsafe production config: " + "; ".join(problems))
