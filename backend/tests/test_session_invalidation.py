"""Changing or resetting the password invalidates previously-issued tokens."""
import re

from app.utils import email


def test_change_password_invalidates_old_token_but_returns_a_fresh_one(client, auth):
    headers, _ = auth(password="OldPass123")

    # The change succeeds using the current token and returns a new one.
    r = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
    )
    assert r.status_code == 200, r.text
    new_token = r.json().get("access_token")
    assert new_token, "change-password should return a fresh access_token"

    # The OLD token is now rejected…
    assert client.get("/auth/me", headers=headers).status_code == 401
    # …and the NEW token works.
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200


def test_reset_invalidates_existing_session(client, auth):
    headers, creds = auth(password="OldPass123")
    # Sanity: token works before the reset.
    assert client.get("/auth/me", headers=headers).status_code == 200

    client.post("/auth/forgot-password", json={"email": creds["email"]})
    body = email.outbox[-1]["body"]
    token = re.search(r"token=([A-Za-z0-9_\-]+)", body).group(1)
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "BrandNew99"}).status_code == 200

    # The session that existed before the reset is now invalid.
    assert client.get("/auth/me", headers=headers).status_code == 401
