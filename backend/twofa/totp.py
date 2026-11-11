"""TOTP helpers (pyotp) + QR provisioning. Used by 2FA (feature-flagged off)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import threading
import time
from datetime import datetime

import pyotp
import qrcode

_ISSUER = "Foroba"

# Replay guard (pre-beta Task 2.2): the last accepted time-step per secret. A code is only
# accepted for a step strictly newer than the last one, so an observed code cannot be
# reused inside its validity window. In-process is enough: the backend runs one uvicorn
# worker; a restart forgets the steps, which reopens at most one 90-second window.
_last_step: dict[str, int] = {}
_lock = threading.Lock()


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, *, account: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=_ISSUER)


def verify_code(secret: str, code: str, *, consume: bool = True) -> bool:
    """`consume=False` is for confirming a pending (not yet active) secret at enrolment:
    that grants nothing, so it does not burn the step the user may need for step-up."""
    totp = pyotp.TOTP(secret)
    now = time.time()
    key = hashlib.sha256(secret.encode()).hexdigest()
    for offset in (-1, 0, 1):
        at = now + offset * totp.interval
        if hmac.compare_digest(totp.at(at), str(code)):
            step = totp.timecode(datetime.fromtimestamp(at))
            if not consume:
                return True
            with _lock:
                if step <= _last_step.get(key, -1):
                    return False
                _last_step[key] = step
            return True
    return False


def qr_data_url(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
