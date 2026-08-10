"""Email delivery for Foroba transactional emails (GL-8.1, foroba#184).

SMTP transport via Brevo (or any SMTP relay). Never raises — a transient SMTP
failure must not flip an otherwise-successful operation to 'failed'. All SMTP
errors are caught and logged, not propagated.

Template system supports EN/FR/IT. Language is derived from the user's country
code (FR/BE → fr, IT → it, everything else → en).
"""

from __future__ import annotations

import logging
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# i18n strings — EN / FR / IT
# ---------------------------------------------------------------------------

_I18N: dict[str, dict[str, str]] = {
    "en": {
        "otp_subject": "Your Foroba verification code",
        "otp_heading": "Your verification code",
        "otp_body": "Use the code below to complete your action on Foroba.",
        "otp_expiry": "This code expires in {minutes} minutes.",
        "verify_subject": "Verify your Foroba email address",
        "verify_heading": "Confirm your email",
        "verify_body": "Welcome to Foroba! Use the code below to verify your email address.",
        "email_change_subject": "Confirm your new Foroba email address",
        "email_change_heading": "Confirm email change",
        "email_change_body": (
            "Someone (hopefully you) requested to change the email address"
            " on a Foroba account to this address. Use the code below to confirm."
        ),
        "invite_subject": "You've been invited to a Foroba household",
        "invite_heading": "Household invitation",
        "invite_body": "{inviter} has invited you to join their household on Foroba.",
        "invite_cta": (
            "Accept this invitation by logging in to Foroba and entering the code below,"
            " or by visiting your household settings."
        ),
        "no_action": "If you did not request this, you can safely ignore this email.",
        "footer": "This message was sent by Foroba. Do not reply to this email.",
    },
    "fr": {
        "otp_subject": "Votre code de vérification Foroba",
        "otp_heading": "Votre code de vérification",
        "otp_body": "Utilisez le code ci-dessous pour finaliser votre action sur Foroba.",
        "otp_expiry": "Ce code expire dans {minutes} minutes.",
        "verify_subject": "Vérifiez votre adresse e-mail Foroba",
        "verify_heading": "Confirmez votre e-mail",
        "verify_body": (
            "Bienvenue sur Foroba\u00a0! Utilisez le code ci-dessous"
            " pour vérifier votre adresse e-mail."
        ),
        "email_change_subject": "Confirmez votre nouvelle adresse e-mail Foroba",
        "email_change_heading": "Confirmation du changement d'e-mail",
        "email_change_body": (
            "Une demande de changement d'adresse e-mail a été effectuée sur votre compte Foroba."
            " Utilisez le code ci-dessous pour confirmer."
        ),
        "invite_subject": "Vous avez été invité(e) dans un foyer Foroba",
        "invite_heading": "Invitation au foyer",
        "invite_body": "{inviter} vous invite à rejoindre son foyer sur Foroba.",
        "invite_cta": (
            "Acceptez cette invitation en vous connectant à Foroba"
            " et en saisissant le code ci-dessous."
        ),
        "no_action": (
            "Si vous n'êtes pas à l'origine de cette demande,"
            " ignorez simplement cet e-mail."
        ),
        "footer": "Ce message a été envoyé par Foroba. Ne répondez pas à cet e-mail.",
    },
    "it": {
        "otp_subject": "Il tuo codice di verifica Foroba",
        "otp_heading": "Il tuo codice di verifica",
        "otp_body": "Usa il codice qui sotto per completare la tua azione su Foroba.",
        "otp_expiry": "Questo codice scade tra {minutes} minuti.",
        "verify_subject": "Verifica il tuo indirizzo email Foroba",
        "verify_heading": "Conferma la tua email",
        "verify_body": (
            "Benvenuto su Foroba! Usa il codice qui sotto"
            " per verificare il tuo indirizzo email."
        ),
        "email_change_subject": "Conferma il tuo nuovo indirizzo email Foroba",
        "email_change_heading": "Conferma cambio email",
        "email_change_body": (
            "È stata richiesta la modifica dell'indirizzo email di un account Foroba"
            " a questo indirizzo. Usa il codice qui sotto per confermare."
        ),
        "invite_subject": "Sei stato invitato in un nucleo familiare Foroba",
        "invite_heading": "Invito al nucleo familiare",
        "invite_body": "{inviter} ti ha invitato a unirti al suo nucleo familiare su Foroba.",
        "invite_cta": "Accetta questo invito accedendo a Foroba e inserendo il codice qui sotto.",
        "no_action": "Se non hai richiesto questo, puoi ignorare questa email.",
        "footer": "Questo messaggio è stato inviato da Foroba. Non rispondere a questa email.",
    },
}

_COUNTRY_TO_LANG: dict[str, str] = {
    "FR": "fr", "BE": "fr", "LU": "fr", "CH": "fr",
    "IT": "it",
}


def _lang(country: str | None) -> str:
    return _COUNTRY_TO_LANG.get((country or "").upper(), "en")


def _t(lang: str, key: str, **kwargs: str) -> str:
    s = _I18N.get(lang, _I18N["en"]).get(key, _I18N["en"][key])
    return s.format(**kwargs) if kwargs else s


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title></head>
<body style="margin:0;padding:0;background:#0F1117;font-family:system-ui,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0F1117;padding:32px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0"
       style="background:#1A1F2E;border-radius:8px;overflow:hidden;max-width:560px;width:100%;">
  <tr><td style="background:#0D9488;padding:24px 32px;">
    <span style="color:#fff;font-size:22px;font-weight:700;letter-spacing:-0.5px;">Foroba</span>
  </td></tr>
  <tr><td style="padding:32px;">
    <h1 style="margin:0 0 16px;color:#F1F5F9;font-size:20px;font-weight:600;">{heading}</h1>
    <p style="margin:0 0 24px;color:#94A3B8;font-size:15px;line-height:1.6;">{body}</p>
    {code_block}
    {extra}
    <p style="margin:24px 0 0;color:#64748B;font-size:13px;">{no_action}</p>
  </td></tr>
  <tr><td style="padding:16px 32px;border-top:1px solid #2D3348;">
    <p style="margin:0;color:#475569;font-size:12px;">{footer}</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>
"""

_CODE_BLOCK = (
    '<div style="background:#0F1117;border:1px solid #2D3348;border-radius:6px;'
    'padding:20px;text-align:center;margin:0 0 16px;">'
    '<span style="font-family:monospace;font-size:32px;font-weight:700;'
    'letter-spacing:8px;color:#0D9488;">{code}</span></div>'
)


def _render_html(
    lang: str,
    subject: str,
    heading: str,
    body: str,
    code: str | None,
    extra: str = "",
    no_action_key: str = "no_action",
) -> tuple[str, str]:
    """Return (html, plain_text) for a transactional email."""
    code_block = _CODE_BLOCK.format(code=code) if code else ""
    html = _HTML_TEMPLATE.format(
        lang=lang,
        subject=subject,
        heading=heading,
        body=body,
        code_block=code_block,
        extra=extra,
        no_action=_t(lang, no_action_key),
        footer=_t(lang, "footer"),
    )
    plain = textwrap.dedent(f"""\
        {heading}

        {body}

        {code if code else ""}

        {_t(lang, no_action_key)}
        ---
        {_t(lang, "footer")}
    """).strip()
    return html, plain


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def _smtp_send(to: str, subject: str, html: str, plain: str) -> None:
    """Low-level SMTP dispatch. Logs but never raises."""
    if not settings.smtp_enabled:
        logger.info("SMTP disabled — would send to %s: %s", to, subject)
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.smtp_from, [to], msg.as_string())
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send email to %s", to)


def send_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text email. Kept for backward-compat (monthly reports)."""
    if not settings.smtp_enabled:
        logger.info("SMTP disabled — would send email to %s: %s", to, subject)
        return
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.smtp_from, [to], message.as_string())
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send email to %s", to)


# ---------------------------------------------------------------------------
# Typed transactional email senders (GL-8.1, foroba#184)
# ---------------------------------------------------------------------------

_OTP_TTL_MINUTES = 10


def send_otp_email(
    to: str, code: str, *, country: str | None = None, ttl_minutes: int = _OTP_TTL_MINUTES
) -> None:
    """Generic OTP code email (2FA, password reset, etc.)."""
    lg = _lang(country)
    subject = _t(lg, "otp_subject")
    html, plain = _render_html(
        lang=lg,
        subject=subject,
        heading=_t(lg, "otp_heading"),
        body=_t(lg, "otp_body"),
        code=code,
        extra=f'<p style="color:#64748B;font-size:13px;margin:0 0 16px;">'
              f'{_t(lg, "otp_expiry", minutes=str(ttl_minutes))}</p>',
    )
    _smtp_send(to, subject, html, plain)


def send_signup_verify_email(
    to: str, code: str, *, country: str | None = None, ttl_minutes: int = _OTP_TTL_MINUTES
) -> None:
    """Welcome + email verification OTP sent at signup."""
    lg = _lang(country)
    subject = _t(lg, "verify_subject")
    html, plain = _render_html(
        lang=lg,
        subject=subject,
        heading=_t(lg, "verify_heading"),
        body=_t(lg, "verify_body"),
        code=code,
        extra=f'<p style="color:#64748B;font-size:13px;margin:0 0 16px;">'
              f'{_t(lg, "otp_expiry", minutes=str(ttl_minutes))}</p>',
    )
    _smtp_send(to, subject, html, plain)


def send_email_change_email(
    to: str, code: str, *, country: str | None = None, ttl_minutes: int = _OTP_TTL_MINUTES
) -> None:
    """OTP to confirm a new email address before applying the change."""
    lg = _lang(country)
    subject = _t(lg, "email_change_subject")
    html, plain = _render_html(
        lang=lg,
        subject=subject,
        heading=_t(lg, "email_change_heading"),
        body=_t(lg, "email_change_body"),
        code=code,
        extra=f'<p style="color:#64748B;font-size:13px;margin:0 0 16px;">'
              f'{_t(lg, "otp_expiry", minutes=str(ttl_minutes))}</p>',
    )
    _smtp_send(to, subject, html, plain)


def send_household_invite_email(
    to: str,
    token: str,
    *,
    inviter_name: str,
    country: str | None = None,
) -> None:
    """Household invite email containing a short accept-token."""
    lg = _lang(country)
    subject = _t(lg, "invite_subject")
    html, plain = _render_html(
        lang=lg,
        subject=subject,
        heading=_t(lg, "invite_heading"),
        body=_t(lg, "invite_body", inviter=inviter_name),
        code=token,
        extra=f'<p style="color:#94A3B8;font-size:14px;margin:0 0 16px;">'
              f'{_t(lg, "invite_cta")}</p>',
    )
    _smtp_send(to, subject, html, plain)
