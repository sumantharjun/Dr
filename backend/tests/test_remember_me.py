"""Tests for Remember Me and sliding sessions."""
from datetime import timedelta

import pytest

from app.config import settings
from app.utils.dependencies import RENEWED_TOKEN_HEADER
from app.utils.security import (
    REMEMBER_CLAIM,
    create_access_token,
    decode_token,
    password_marker,
    renew_if_stale,
    session_lifetime,
)


def _register(client, email):
    r = client.post(
        "/auth/register",
        json={"email": email, "full_name": "T", "password": "Sup3rSecret!"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _login(client, email, remember):
    r = client.post(
        "/auth/login",
        json={"email": email, "password": "Sup3rSecret!", "remember_me": remember},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _ttl_minutes(token):
    """Approximate remaining lifetime, on the same scale the token encodes."""
    from app.utils.security import _now_as_encoded_timestamp

    return (decode_token(token)["exp"] - _now_as_encoded_timestamp()) / 60


# ── lifetime selection ──────────────────────────────────────────────────────

def test_remember_me_issues_long_session(client):
    _register(client, "rm1@test.com")
    token = _login(client, "rm1@test.com", remember=True)
    payload = decode_token(token)
    assert payload[REMEMBER_CLAIM] is True
    assert _ttl_minutes(token) == pytest.approx(settings.REMEMBER_ME_EXPIRE_MINUTES, rel=0.01)


def test_without_remember_me_issues_short_session(client):
    _register(client, "rm2@test.com")
    token = _login(client, "rm2@test.com", remember=False)
    payload = decode_token(token)
    assert payload[REMEMBER_CLAIM] is False
    assert _ttl_minutes(token) == pytest.approx(settings.ACCESS_TOKEN_EXPIRE_MINUTES, rel=0.01)


def test_remember_me_defaults_to_false_for_old_clients(client):
    """A client that doesn't send the field must not silently get a 30-day token."""
    _register(client, "rm3@test.com")
    r = client.post("/auth/login", json={"email": "rm3@test.com", "password": "Sup3rSecret!"})
    assert r.status_code == 200, r.text
    assert decode_token(r.json()["access_token"])[REMEMBER_CLAIM] is False


def test_register_issues_a_remembered_session(client):
    token = _register(client, "rm4@test.com")
    assert decode_token(token)[REMEMBER_CLAIM] is True


# ── sliding renewal ─────────────────────────────────────────────────────────

def test_fresh_token_is_not_renewed(client):
    _register(client, "rm5@test.com")
    token = _login(client, "rm5@test.com", remember=True)
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert RENEWED_TOKEN_HEADER not in r.headers, "a brand-new token must not renew"


def test_half_expired_token_is_renewed_on_a_real_request(client):
    """The core of the feature: an old-but-valid token comes back refreshed."""
    _register(client, "rm6@test.com")
    user_id = decode_token(_login(client, "rm6@test.com", remember=True))["sub"]

    lifetime = session_lifetime(True)
    stale = create_access_token(
        {"sub": user_id, "pwd_at": "", REMEMBER_CLAIM: True},
        expires_delta=lifetime * 0.4,  # past halfway
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {stale}"})
    assert r.status_code == 200, r.text
    renewed = r.headers.get(RENEWED_TOKEN_HEADER)
    assert renewed, "expected a renewed token"
    assert _ttl_minutes(renewed) == pytest.approx(settings.REMEMBER_ME_EXPIRE_MINUTES, rel=0.01)
    # The replacement must still work, and must stay a remembered session.
    assert decode_token(renewed)[REMEMBER_CLAIM] is True
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {renewed}"}).status_code == 200


def test_renewal_preserves_short_lifetime_for_unremembered(client):
    """Sliding must not silently promote a session-only login to 30 days."""
    _register(client, "rm7@test.com")
    user_id = decode_token(_login(client, "rm7@test.com", remember=False))["sub"]
    stale = create_access_token(
        {"sub": user_id, "pwd_at": "", REMEMBER_CLAIM: False},
        expires_delta=session_lifetime(False) * 0.4,
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {stale}"})
    renewed = r.headers.get(RENEWED_TOKEN_HEADER)
    assert renewed
    assert decode_token(renewed)[REMEMBER_CLAIM] is False
    assert _ttl_minutes(renewed) == pytest.approx(settings.ACCESS_TOKEN_EXPIRE_MINUTES, rel=0.01)


def test_expired_token_is_rejected_not_renewed(client):
    """An expired session must die, not resurrect itself."""
    _register(client, "rm8@test.com")
    user_id = decode_token(_login(client, "rm8@test.com", remember=True))["sub"]
    dead = create_access_token(
        {"sub": user_id, "pwd_at": "", REMEMBER_CLAIM: True},
        expires_delta=timedelta(minutes=-5),
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {dead}"})
    assert r.status_code == 401
    assert RENEWED_TOKEN_HEADER not in r.headers


def test_renew_if_stale_is_pure_on_a_fresh_payload():
    payload = decode_token(
        create_access_token({"sub": "1", "pwd_at": "", REMEMBER_CLAIM: True},
                            expires_delta=session_lifetime(True))
    )
    assert renew_if_stale(payload) is None


def test_renew_if_stale_handles_token_without_exp():
    assert renew_if_stale({"sub": "1", "pwd_at": ""}) is None


# ── interaction with existing session rules ─────────────────────────────────

def test_password_change_keeps_remembered_lifetime(client):
    _register(client, "rm9@test.com")
    token = _login(client, "rm9@test.com", remember=True)
    r = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Sup3rSecret!", "new_password": "Even5tronger!"},
    )
    assert r.status_code == 200, r.text
    new_token = r.json()["access_token"]
    assert decode_token(new_token)[REMEMBER_CLAIM] is True
    assert _ttl_minutes(new_token) == pytest.approx(settings.REMEMBER_ME_EXPIRE_MINUTES, rel=0.01)


def test_password_change_still_invalidates_a_remembered_session(client):
    """A 30-day token must not survive a password change — that's the only
    revocation lever this design has."""
    _register(client, "rm10@test.com")
    old = _login(client, "rm10@test.com", remember=True)
    client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {old}"},
        json={"current_password": "Sup3rSecret!", "new_password": "Even5tronger!"},
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {old}"})
    assert r.status_code == 401, "old long-lived token should be dead"


def test_renewal_cannot_outlive_a_password_change(client):
    """A stale token whose password marker no longer matches must 401 rather
    than being handed a fresh 30-day replacement."""
    _register(client, "rm11@test.com")
    token = _login(client, "rm11@test.com", remember=True)
    user_id = decode_token(token)["sub"]
    client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Sup3rSecret!", "new_password": "Even5tronger!"},
    )
    stale_with_old_marker = create_access_token(
        {"sub": user_id, "pwd_at": "", REMEMBER_CLAIM: True},
        expires_delta=session_lifetime(True) * 0.4,
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {stale_with_old_marker}"})
    assert r.status_code == 401
    assert RENEWED_TOKEN_HEADER not in r.headers


def test_cors_exposes_the_renewal_header():
    """Without expose_headers the browser hides X-Renewed-Token from JS and
    sliding sessions silently stop working in production."""
    from app.main import app
    from fastapi.middleware.cors import CORSMiddleware

    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors, "CORS middleware not installed"
    assert RENEWED_TOKEN_HEADER in cors[0].kwargs.get("expose_headers", [])
