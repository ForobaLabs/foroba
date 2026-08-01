"""Shared slowapi Limiter instance.

Split out from main.py so auth/router.py and twofa/router.py can apply
per-endpoint rate limits without a circular import (main.py imports those
routers).
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
