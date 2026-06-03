"""
Minimal outbound-email helper.

If SMTP is configured (settings.SMTP_HOST set), messages are sent via smtplib.
Otherwise — local dev / tests / no mail server — they're logged and appended to
an in-memory `outbox`, so flows that send email stay fully testable without a
real SMTP server. Tests can assert on `email.outbox`.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory record of messages (used in dev/test when SMTP isn't configured).
outbox: list[dict] = []


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        # No mail server configured (dev/test) — record to the in-memory outbox
        # (tests assert on it) and log. NOT done when SMTP is configured, so the
        # outbox can't grow unbounded in production.
        outbox.append({"to": to, "subject": subject, "body": body})
        logger.info("[email:dev] To=%s Subject=%s\n%s", to, subject, body)
        return

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
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
