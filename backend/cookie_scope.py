"""Which `Domain` a Foroba-issued cookie gets.

`COOKIE_DOMAIN` (e.g. ".forobalabs.com") is applied only when the request host is that domain
or a subdomain of it. Any other host (DuckDNS during the transition, localhost, look-alikes such
as "evilforobalabs.com") keeps a host-only cookie.
"""

from __future__ import annotations

from config import settings


def cookie_domain_for(host: str | None) -> str | None:
    configured = (settings.cookie_domain or "").strip().lower()
    if not configured or not host:
        return None
    bare = configured.lstrip(".")
    name = host.strip().lower().rsplit(":", 1)[0] if ":" in host else host.strip().lower()
    if name == bare or name.endswith("." + bare):
        return configured
    return None
