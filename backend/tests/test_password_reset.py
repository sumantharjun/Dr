"""Forgot / reset password: single-use, time-limited link; no enumeration."""
import re

from app.utils import email
from app.database import SessionLocal
from app.models.password_reset import PasswordResetToken
from app.utils.timezone import now_ist
from datetime import timedelta


def _token_from_outbox() -> str:
    assert email.outbox, "expected a reset email in the outbox"
    body = email.outbox[-1]["body"]
    m = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert m, f"no reset token in email body:\n{body}"
    return m.group(1)


def test_full_reset_flow(client, auth):
    headers, creds = auth(password="OldPass123")

    # Request a reset.
    r = client.post("/auth/forgot-password", json={"email": creds["email"]})
    assert r.status_code == 200
    token = _token_from_outbox()

    # Reset with the token.
    r = client.post("/auth/reset-password", json={"token": token, "new_password": "BrandNew99"})
    assert r.status_code == 200, r.text

    # Old password no longer works; the new one does.
    assert client.post("/auth/login", json={"email": creds["email"], "password": "OldPass123"}).status_code == 401
    assert client.post("/auth/login", json={"email": creds["email"], "password": "BrandNew99"}).status_code == 200


def test_token_is_single_use(client, auth):
    _, creds = auth(password="OldPass123")
    client.post("/auth/forgot-password", json={"email": creds["email"]})
    token = _token_from_outbox()

    assert client.post("/auth/reset-password", json={"token": token, "new_password": "FirstReset1"}).status_code == 200
    # Reusing the same token must fail.
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "SecondTry2"}).status_code == 400


def test_no_account_enumeration(client):
    # Unknown email returns the SAME 200 message and sends no email.
    r = client.post("/auth/forgot-password", json={"email": "nobody@nowhere.com"})
    assert r.status_code == 200
    assert "If an account exists" in r.json()["message"]
    assert email.outbox == []


def test_invalid_token_rejected(client):
    assert client.post(
        "/auth/reset-password", json={"token": "not-a-real-token", "new_password": "Whatever12"}
    ).status_code == 400


def test_expired_token_rejected(client, auth):
    _, creds = auth(password="OldPass123")
    client.post("/auth/forgot-password", json={"email": creds["email"]})
    token = _token_from_outbox()

    # Force the token to be expired.
    db = SessionLocal()
    row = db.query(PasswordResetToken).order_by(PasswordResetToken.id.desc()).first()
    row.expires_at = now_ist() - timedelta(minutes=1)
    db.commit(); db.close()

    assert client.post(
        "/auth/reset-password", json={"token": token, "new_password": "TooLate123"}
    ).status_code == 400


def test_new_reset_invalidates_previous(client, auth):
    _, creds = auth(password="OldPass123")
    client.post("/auth/forgot-password", json={"email": creds["email"]})
    first = _token_from_outbox()
    client.post("/auth/forgot-password", json={"email": creds["email"]})
    second = _token_from_outbox()
    assert first != second

    # The first (superseded) token no longer works; the newest does.
    assert client.post("/auth/reset-password", json={"token": first, "new_password": "Nope123456"}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": second, "new_password": "Yes1234567"}).status_code == 200
