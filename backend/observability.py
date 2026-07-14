"""Self-hosted error tracking via GlitchTip (TI-B item 2, foroba#153).

Uses sentry-sdk pointed at a self-hosted GlitchTip DSN instead of Sentry SaaS.
No performance tracing (traces_sample_rate=0) — GlitchTip's APM support is
immature and /health/detailed already covers dependency-level slowness.

Privacy: `scrub_event` strips the request body and any sensitive breadcrumb
data unconditionally before an event ever leaves the process, even though
GlitchTip is self-hosted — no user financial data should ever be sent.
"""
from __future__ import annotations

from typing import Any

import sentry_sdk

_SENSITIVE_BREADCRUMB_CATEGORIES = {"http", "query"}


def scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    request = event.get("request")
    if request and "data" in request:
        del request["data"]

    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        for crumb in breadcrumbs.get("values", []):
            if crumb.get("category") in _SENSITIVE_BREADCRUMB_CATEGORIES and crumb.get("data"):
                crumb["data"] = {}

    return event


def init_error_tracking(dsn: str) -> None:
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0,
        send_default_pii=False,
        before_send=scrub_event,
    )
