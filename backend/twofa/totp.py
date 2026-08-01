"""TOTP helpers (pyotp) + QR provisioning. Used by 2FA (feature-flagged off)."""

from __future__ import annotations

import base64
import io

import pyotp
import qrcode

_ISSUER = "Foroba"


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, *, account: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=_ISSUER)


def verify_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def qr_data_url(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
