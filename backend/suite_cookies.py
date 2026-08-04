"""foroba#206: shared helper to build the cookie dict forwarded on every outgoing
Pazuru/Tsumi cross-app httpx call.

Since foroba#199 (MFA/step-up session hardening), both Pazuru's and Tsumi's
require_auth additionally require the destination app's own short-lived
stepup_<app> cookie on every authenticated request. Every cross-app service file
in this backend forwarded only suite_session, so every such call has been failing
upstream with 428 and getting silently swallowed into a "degraded" empty response
since foroba#199 shipped -- this helper centralizes correct forwarding.
"""

from __future__ import annotations


def suite_cookies(
    suite_session: str | None,
    *,
    stepup_pazuru: str | None = None,
    stepup_tsumi: str | None = None,
) -> dict[str, str] | None:
    """Build the cookies dict to pass to httpx for a cross-app call. Includes
    whichever of suite_session/stepup_pazuru/stepup_tsumi are present on the
    inbound request -- harmless to forward a stepup cookie to an app that
    doesn't need it, so callers needing both apps just pass both."""
    cookies: dict[str, str] = {}
    if suite_session:
        cookies["suite_session"] = suite_session
    if stepup_pazuru:
        cookies["stepup_pazuru"] = stepup_pazuru
    if stepup_tsumi:
        cookies["stepup_tsumi"] = stepup_tsumi
    return cookies or None
