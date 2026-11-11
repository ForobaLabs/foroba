"""Origin check for state-changing requests (pre-beta Task 2.2, CSRF defence in depth).

suite_session is SameSite=Lax, which already stops cross-site POSTs in modern browsers;
this refuses any unsafe request whose Origin header names a site outside ALLOWED_ORIGINS.
Requests without an Origin (native app, server-to-server, webhooks) pass: the browser
always sends Origin on a cross-origin POST/PUT/PATCH/DELETE.
"""

from __future__ import annotations

from collections.abc import Iterable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class OriginCheckMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str]) -> None:
        self.app = app
        self.allowed = {o.strip().rstrip("/") for o in allowed_origins if o.strip()}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in _UNSAFE:
            origin = dict(scope["headers"]).get(b"origin")
            if origin is not None and origin.decode("latin-1").rstrip("/") not in self.allowed:
                response = JSONResponse({"detail": "Cross-origin request refused"}, 403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
