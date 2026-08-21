"""Tests for the first-run guided tour flag (users.tour_completed_at)."""


def test_new_account_has_not_seen_the_tour(client, auth):
    """NULL is what triggers the tour on first login."""
    headers, _ = auth()
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["tour_completed_at"] is None


def test_register_response_carries_the_flag(client):
    """The client decides whether to start the tour straight from sign-up."""
    r = client.post("/auth/register", json={
        "email": "tour1@test.com", "full_name": "T", "password": "Sup3rSecret!"})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["tour_completed_at"] is None


def test_completing_the_tour_is_recorded(client, auth):
    headers, _ = auth()
    r = client.post("/auth/me/tour?completed=true", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["tour_completed_at"] is not None
    # And it must survive the read path, not just echo back.
    assert client.get("/auth/me", headers=headers).json()["tour_completed_at"] is not None


def test_tour_defaults_to_completed_when_the_flag_is_omitted(client, auth):
    headers, _ = auth()
    r = client.post("/auth/me/tour", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["tour_completed_at"] is not None


def test_replaying_clears_the_flag(client, auth):
    """What the Settings "Replay tour" button does."""
    headers, _ = auth()
    client.post("/auth/me/tour?completed=true", headers=headers)
    r = client.post("/auth/me/tour?completed=false", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["tour_completed_at"] is None


def test_tour_state_requires_auth(client):
    assert client.post("/auth/me/tour?completed=true").status_code == 403


def test_tour_state_is_per_account(client, auth):
    a, _ = auth()
    b, _ = auth()
    client.post("/auth/me/tour?completed=true", headers=a)
    assert client.get("/auth/me", headers=a).json()["tour_completed_at"] is not None
    assert client.get("/auth/me", headers=b).json()["tour_completed_at"] is None, \
        "one account finishing the tour must not silence it for another"
