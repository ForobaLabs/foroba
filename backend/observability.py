"""Self-hosted error tracking via GlitchTip (TI-B item 2, foroba#153).

Uses sentry-sdk pointed at a self-hosted GlitchTip DSN instead of Sentry SaaS.
No performance tracing (traces_sample_rate=0) — GlitchTip's APM support is
immature and /health/detailed already covers dependency-level slowness.

Privacy: `scrub_event` strips the request body and any sensitive breadcrumb
data unconditionally before an event ever leaves the process, even though
GlitchTip is self-hosted — no user financial data should ever be sent.

GL-11.5 hardening: also strips a fixed set of known-sensitive field names from
`event["extra"]`/`event["contexts"]` (and any nested dicts within them), in case
a future `sentry_sdk.set_context`/`set_extra` call ever includes one of these —
defense in depth on top of the request/breadcrumb scrubbing above.
"""
from __future__ import annotations

from typing import Any

import sentry_sdk

_SENSITIVE_BREADCRUMB_CATEGORIES = {"http", "query"}

# Known-sensitive field names (GL-11.5) — stripped wherever they appear in
# event["extra"]/event["contexts"], however deeply nested.
_SENSITIVE_KEYS = {
    "external_id", "raw_label", "iban", "session_id_enc",
    "content", "code", "raw_text",
}


def _scrub_sensitive_keys(data: dict[str, Any]) -> None:
    for key in list(data.keys()):
        if key in _SENSITIVE_KEYS:
            del data[key]
        elif isinstance(data[key], dict):
            _scrub_sensitive_keys(data[key])


def scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    request = event.get("request")
    if request and "data" in request:
        del request["data"]

    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        for crumb in breadcrumbs.get("values", []):
            if crumb.get("category") in _SENSITIVE_BREADCRUMB_CATEGORIES and crumb.get("data"):
                crumb["data"] = {}

    extra = event.get("extra")
    if isinstance(extra, dict):
        _scrub_sensitive_keys(extra)

    contexts = event.get("contexts")
    if isinstance(contexts, dict):
        _scrub_sensitive_keys(contexts)

    return event


def init_error_tracking(dsn: str) -> None:
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0,
        send_default_pii=False,
        before_send=scrub_event,
    )
