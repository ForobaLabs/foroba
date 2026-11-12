"""SSRF guard for user-supplied outbound URLs (webhooks).

Creation time checks syntax only (so a temporarily unresolvable host can still be
registered). Delivery time passes ``resolve=True`` and additionally requires every
resolved address to be globally routable, which also defeats DNS rebinding between
registration and delivery.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

_BLOCKED_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".lan",
    ".home",
    ".corp",
    ".intranet",
    ".private",
)


class UnsafeUrlError(ValueError):
    """The URL is not an acceptable public HTTPS target."""


def _check_ip(raw: str) -> None:
    ip = ipaddress.ip_address(raw)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if not ip.is_global:
        raise UnsafeUrlError("target resolves to a non-public address")


def assert_public_https_url(url: str, *, resolve: bool = False) -> str:
    try:
        parts = urlsplit(url)
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError on a malformed port
    except ValueError as exc:
        raise UnsafeUrlError("malformed URL") from exc
    if parts.scheme != "https":
        raise UnsafeUrlError("target_url must use https://")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrlError("credentials in the URL are not allowed")
    if not host:
        raise UnsafeUrlError("missing host")
    host = host.rstrip(".").lower()

    try:
        _check_ip(host)
        return url  # public IP literal
    except UnsafeUrlError:
        raise
    except ValueError:
        pass  # not an IP literal: a hostname

    labels = host.split(".")
    if len(labels) < 2 or host.endswith(_BLOCKED_SUFFIXES):
        raise UnsafeUrlError("internal hostnames are not allowed")
    # decimal / hex / octal IPv4 shorthands (2130706433, 0x7f000001, 127.1)
    if labels[-1].isdigit() or labels[-1].startswith("0x"):
        raise UnsafeUrlError("numeric host forms are not allowed")

    if resolve:
        try:
            infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            raise UnsafeUrlError("host does not resolve") from exc
        for info in infos:
            _check_ip(info[4][0])
    return url
