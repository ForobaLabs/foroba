"""Public waitlist endpoints for the Foroba Labs site (Plan D, S1).

Unauthenticated by design; protected by per-IP rate limits, strict validation and a
double opt-in. The POST answers identically for new, pending and confirmed addresses so
the endpoint cannot be used to test list membership.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

import waitlist_service as ws
from auth.conn import get_conn
from config import settings
from email_service import send_email
from rate_limit import limiter

router = APIRouter(prefix="/api/public/v1/waitlist", tags=["waitlist"])

_SUBJECT = {
    "en": "Confirm your place on the Foroba Labs waitlist",
    "it": "Conferma il tuo posto nella lista d'attesa di Foroba Labs",
    "fr": "Confirmez votre place sur la liste d'attente Foroba Labs",
}
_BODY = {
    "en": (
        "Open this link to confirm (valid until used):\n{link}\n\n"
        "If you did not ask for this, ignore this email."
    ),
    "it": (
        "Apri questo link per confermare (valido fino al primo uso):\n{link}\n\n"
        "Se non sei stato tu, ignora questa email."
    ),
    "fr": (
        "Ouvrez ce lien pour confirmer (valable jusqu'à utilisation) :\n{link}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail."
    ),
}


class WaitlistIn(BaseModel):
    email: str = Field(max_length=320)
    apps: list[str] = Field(default_factory=list, max_length=3)
    lang: str = Field(default="en", max_length=5)
    consent: bool = False


@router.post("", status_code=202)
@limiter.limit("5/hour")
def join_waitlist(
    request: Request, body: WaitlistIn, conn: sqlite3.Connection = Depends(get_conn)
):
    try:
        token = ws.join(
            conn, email=body.email, apps=body.apps, lang=body.lang, consent=body.consent
        )
    except ws.WaitlistError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=422)
    if token:
        lang = body.lang if body.lang in ws.ALLOWED_LANGS else "en"
        link = f"{str(request.base_url).rstrip('/')}{router.prefix}/confirm?token={token}"
        send_email(body.email.strip().lower(), _SUBJECT[lang], _BODY[lang].format(link=link))
    return {"status": "pending"}


@router.get("/confirm")
@limiter.limit("30/hour")
def confirm_waitlist(
    request: Request, token: str = "", conn: sqlite3.Connection = Depends(get_conn)
):
    lang_row = conn.execute(
        "SELECT lang FROM waitlist WHERE confirm_token_hash = ?", (ws.hash_token(token),)
    ).fetchone()
    ok = ws.confirm(conn, token)
    base = settings.site_base_url.rstrip("/")
    if not base:
        return {"confirmed": ok}
    lang = lang_row[0] if (ok and lang_row) else "en"
    state = "confirmed" if ok else "invalid"
    return RedirectResponse(f"{base}/{lang}/contact.html?waitlist={state}", status_code=303)
