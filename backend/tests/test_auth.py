"""Auth flow: register, login, /me, and the guards around them."""


def test_register_login_me(client, auth):
    headers, creds = auth()

    # /me returns the registered user
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == creds["email"]

    # login with the same credentials works
    r = client.post("/auth/login", json={"email": creds["email"], "password": creds["password"]})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_register_duplicate_email_rejected(client, auth):
    _, creds = auth()
    r = client.post(
        "/auth/register",
        json={"email": creds["email"], "full_name": "Dup", "password": "Sup3rSecret!"},
    )
    assert r.status_code == 400


def test_login_wrong_password_rejected(client, auth):
    _, creds = auth()
    r = client.post("/auth/login", json={"email": creds["email"], "password": "wrong-password"})
    assert r.status_code == 401


def test_register_short_password_rejected(client):
    r = client.post(
        "/auth/register",
        json={"email": "shorty@test.com", "full_name": "S", "password": "short"},
    )
    assert r.status_code == 422  # pydantic validation


def test_protected_route_requires_token(client):
    assert client.get("/auth/me").status_code in (401, 403)


def test_register_rate_limited(client):
    # register_limiter allows 3 / 5 min per IP; the 4th must 429.
    codes = []
    for i in range(4):
        r = client.post(
            "/auth/register",
            json={"email": f"rl{i}@test.com", "full_name": "RL", "password": "Sup3rSecret!"},
        )
        codes.append(r.status_code)
    assert codes[:3] == [201, 201, 201]
    assert codes[3] == 429
