"""POST /auth/change-password."""


def test_change_password_happy_path(client, auth):
    headers, creds = auth(password="OldPass123")

    r = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
    )
    assert r.status_code == 200, r.text

    # Old password no longer works; new one does.
    assert client.post("/auth/login", json={"email": creds["email"], "password": "OldPass123"}).status_code == 401
    assert client.post("/auth/login", json={"email": creds["email"], "password": "NewPass456"}).status_code == 200


def test_wrong_current_password_rejected(client, auth):
    headers, _ = auth(password="OldPass123")
    r = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "WRONG", "new_password": "NewPass456"},
    )
    assert r.status_code == 400


def test_new_password_too_short_rejected(client, auth):
    headers, _ = auth(password="OldPass123")
    r = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "OldPass123", "new_password": "short"},
    )
    assert r.status_code == 422  # pydantic min-length


def test_change_password_requires_auth(client):
    assert client.post(
        "/auth/change-password",
        json={"current_password": "x", "new_password": "yyyyyyyy"},
    ).status_code in (401, 403)
