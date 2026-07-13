"""
Minimal outbound-email helper.

If SMTP is configured (settings.SMTP_HOST set), messages are sent via smtplib.
Otherwise — local dev / tests / no mail server — they're logged and appended to
an in-memory `outbox`, so flows that send email stay fully testable without a
real SMTP server. Tests can assert on `email.outbox`.
"""
import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory record of messages (used in dev/test when no transport is configured).
outbox: list[dict] = []

RESEND_ENDPOINT = "https://api.resend.com/emails"


def _send_via_resend(to: str, subject: str, body: str) -> None:
    """Send through Resend's HTTPS API (port 443). Preferred transport."""
    payload = json.dumps({
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "text": body,
    }).encode()
    req = urllib.request.Request(
        RESEND_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            # A non-default User-Agent avoids Cloudflare's bot block on the
            # stdlib's "Python-urllib/x.y" default.
            "User-Agent": "unova-backend/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            logger.info("Sent email to %s via Resend (subject=%s, status=%s)", to, subject, resp.status)
    except urllib.error.HTTPError as e:
        # Surface Resend's actual rejection (e.g. unverified-domain sandbox
        # limit) in the logs so failures aren't invisible. Still not raised to
        # the caller — the API response must not reveal whether the email exists.
        detail = e.read().decode(errors="replace")
        logger.error("Resend rejected email to %s (HTTP %s): %s", to, e.code, detail)
    except Exception:
        logger.exception("Failed to send email to %s via Resend", to)


def send_email(to: str, subject: str, body: str) -> None:
    if settings.RESEND_API_KEY:
        _send_via_resend(to, subject, body)
        return

    if not settings.SMTP_HOST:
        # No transport configured (dev/test) — record to the in-memory outbox
        # (tests assert on it) and log. NOT done when a transport is configured,
        # so the outbox can't grow unbounded in production.
        outbox.append({"to": to, "subject": subject, "body": body})
        logger.info("[email:dev] To=%s Subject=%s\n%s", to, subject, body)
        return

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        # Port 465 uses implicit TLS (SSL on connect); 587 uses STARTTLS. Many
        # networks block 587, so 465/SSL is the more reliable default. Branch on
        # the port, which is the standard SMTP convention.
        if settings.SMTP_PORT == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15, context=ctx) as smtp:
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls(context=ssl.create_default_context())
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
        logger.info("Sent email to %s (subject=%s)", to, subject)
    except Exception:
        # Never surface SMTP errors to the caller — the API response must not
        # reveal whether the address exists, and a mail hiccup shouldn't 500.
        logger.exception("Failed to send email to %s", to)


def send_password_reset_email(to: str, reset_url: str, expire_minutes: int) -> None:
    subject = "Reset your UNOVA password"
    body = (
        "We received a request to reset your UNOVA password.\n\n"
        f"Reset it using this link (valid for {expire_minutes} minutes, single use):\n"
        f"{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email — your "
        "password won't change.\n"
    )
    send_email(to, subject, body)
