"""Invite code generation (GL-10.1, foroba#185). Mirrors recovery_codes.py's pattern."""

from __future__ import annotations

import secrets

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars (0/O, 1/I/L)
_GROUP_LENGTH = 4
_GROUP_COUNT = 2


def generate_code() -> str:
    groups = [
        "".join(secrets.choice(_ALPHABET) for _ in range(_GROUP_LENGTH))
        for _ in range(_GROUP_COUNT)
    ]
    return "-".join(groups)
