"""
Tests for Google Sign-In (POST /auth/google).

Fully offline and deterministic: we generate an RSA keypair in-process, sign our
own ID tokens with it, and stub the JWKS fetch to return the matching public key.
Nothing here touches Google. Same discipline as tests/test_exchange_rates.py.
"""
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.config import settings
from app.models.auth_identity import AuthIdentity
from app.models.user import User
from app.services import oauth_google
from app.utils.security import REMEMBER_CLAIM, decode_token

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
KID = "test-key-1"

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_priv_pem = _key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()


def _jwks() -> dict:
    """Our public key, in the shape Google's certs endpoint returns."""
    from jose import jwk

    pub = jwk.construct(_key.public_key(), algorithm="RS256").to_dict()
    # jose returns bytes for n/e; the real endpoint sends strings.
    pub = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in pub.items()}
    pub.update({"kid": KID, "use": "sig", "alg": "RS256"})
    return {"keys": [pub]}


def _token(**overrides) -> str:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-sub-1",
        "email": "parent@gmail.com",
        "email_verified": True,
        "name": "Parent Person",
        "iat": int(time.time()) - 10,
        "exp": int(time.time()) + 600,
    }
    claims.update(overrides)
    return jwt.encode(claims, _priv_pem, algorithm="RS256", headers={"kid": KID})


@pytest.fixture(autouse=True)
def _google_env(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(oauth_google, "_fetch_jwks", _jwks)
    oauth_google.reset_cache()
    from app.utils.rate_limiter import oauth_limiter
    oauth_limiter._log.clear()
    yield
    oauth_google.reset_cache()


def _post(client, **kw):
    return client.post("/auth/google", json={"credential": _token(**kw)})


# ── happy paths ─────────────────────────────────────────────────────────────

def test_new_user_is_created(client):
    r = client.post("/auth/google", json={"credential": _token(sub="s-new", email="new@gmail.com")})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email"] == "new@gmail.com"
    assert r.json()["user"]["full_name"] == "Parent Person"
    assert r.json()["access_token"]


def test_identity_row_is_written(client):
    from app.database import SessionLocal

    client.post("/auth/google", json={"credential": _token(sub="s-ident", email="i@gmail.com")})
    db = SessionLocal()
    try:
        row = db.query(AuthIdentity).filter(AuthIdentity.provider_user_id == "s-ident").first()
        assert row is not None
        assert row.provider == "google"
        assert row.email_at_link == "i@gmail.com"
    finally:
        db.close()


def test_returning_user_is_matched_by_sub_not_email(client):
    """Identity must survive the parent changing their Google email."""
    from app.database import SessionLocal

    first = client.post("/auth/google", json={"credential": _token(sub="s-stable", email="old@gmail.com")})
    assert first.status_code == 200, first.text
    uid = first.json()["user"]["id"]

    second = client.post("/auth/google", json={"credential": _token(sub="s-stable", email="new@gmail.com")})
    assert second.status_code == 200, second.text
    assert second.json()["user"]["id"] == uid, "same sub must resolve to the same user"

    db = SessionLocal()
    try:
        assert db.query(AuthIdentity).filter(
            AuthIdentity.provider_user_id == "s-stable").count() == 1, "must not duplicate the identity"
    finally:
        db.close()


def test_links_to_existing_password_account(client):
    """The linking rule: same verified email joins the existing account."""
    reg = client.post("/auth/register", json={
        "email": "both@gmail.com", "full_name": "Both", "password": "Sup3rSecret!"})
    assert reg.status_code == 201, reg.text
    uid = reg.json()["user"]["id"]

    r = client.post("/auth/google", json={"credential": _token(sub="s-link", email="both@gmail.com")})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["id"] == uid, "should link, not create a second account"


def test_linking_preserves_password_login(client):
    """Linking Google must not lock the parent out of their password."""
    client.post("/auth/register", json={
        "email": "keep@gmail.com", "full_name": "Keep", "password": "Sup3rSecret!"})
    client.post("/auth/google", json={"credential": _token(sub="s-keep", email="keep@gmail.com")})
    r = client.post("/auth/login", json={"email": "keep@gmail.com", "password": "Sup3rSecret!"})
    assert r.status_code == 200, r.text


def test_missing_name_falls_back_to_email_local_part(client):
    """full_name is NOT NULL and Google may omit `name` (Apple usually will)."""
    r = client.post("/auth/google", json={
        "credential": _token(sub="s-noname", email="anon@gmail.com", name=None)})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["full_name"] == "anon"


# ── the takeover guard ──────────────────────────────────────────────────────

def test_unverified_email_is_refused(client):
    """Without this check, an attacker could claim an existing account by
    creating a Google account on someone else's address."""
    r = client.post("/auth/google", json={
        "credential": _token(sub="s-eve", email="victim@gmail.com", email_verified=False)})
    assert r.status_code == 401, r.text


def test_unverified_email_does_not_create_a_user(client):
    from app.database import SessionLocal

    client.post("/auth/google", json={
        "credential": _token(sub="s-eve2", email="ghost@gmail.com", email_verified=False)})
    db = SessionLocal()
    try:
        assert db.query(User).filter(User.email == "ghost@gmail.com").first() is None
    finally:
        db.close()


# ── token rejection ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad,label", [
    ({"aud": "someone-elses-client-id"}, "wrong audience"),
    ({"iss": "https://evil.example.com"}, "wrong issuer"),
    ({"exp": int(time.time()) - 60}, "expired"),
    ({"email": None}, "no email"),
    ({"sub": None}, "no subject"),
])
def test_bad_tokens_rejected(client, bad, label):
    r = client.post("/auth/google", json={"credential": _token(**bad)})
    assert r.status_code == 401, f"{label} should be refused: {r.text}"


def test_tampered_signature_rejected(client):
    tok = _token()
    head, payload, sig = tok.split(".")
    forged = f"{head}.{payload}.{'A' * len(sig)}"
    r = client.post("/auth/google", json={"credential": forged})
    assert r.status_code == 401, r.text


def test_token_signed_by_a_different_key_rejected(client):
    """A valid-looking token from a key that isn't in Google's JWKS."""
    rogue = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rogue.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    tok = jwt.encode(
        {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "s-rogue",
         "email": "r@gmail.com", "email_verified": True,
         "exp": int(time.time()) + 600},
        pem, algorithm="RS256", headers={"kid": KID},
    )
    r = client.post("/auth/google", json={"credential": tok})
    assert r.status_code == 401, r.text


def test_garbage_credential_rejected(client):
    r = client.post("/auth/google", json={"credential": "not-a-jwt"})
    assert r.status_code == 401, r.text


def test_endpoint_unavailable_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    r = client.post("/auth/google", json={"credential": _token()})
    assert r.status_code == 503, r.text


# ── session semantics ───────────────────────────────────────────────────────

def test_remember_me_controls_session_length(client):
    long_r = client.post("/auth/google", json={
        "credential": _token(sub="s-rm1", email="rm1@gmail.com"), "remember_me": True})
    short_r = client.post("/auth/google", json={
        "credential": _token(sub="s-rm2", email="rm2@gmail.com"), "remember_me": False})
    assert decode_token(long_r.json()["access_token"])[REMEMBER_CLAIM] is True
    assert decode_token(short_r.json()["access_token"])[REMEMBER_CLAIM] is False


def test_issued_token_authenticates_normally(client):
    r = client.post("/auth/google", json={"credential": _token(sub="s-me", email="me@gmail.com")})
    token = r.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "me@gmail.com"


# ── knock-on effects on password flows ──────────────────────────────────────

def test_change_password_on_google_only_account_is_400_not_500(client):
    r = client.post("/auth/google", json={"credential": _token(sub="s-nopw", email="nopw@gmail.com")})
    token = r.json()["access_token"]
    resp = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "anything", "new_password": "Sup3rSecret!"},
    )
    assert resp.status_code == 400, resp.text
    assert "google" in resp.json()["detail"].lower()


def test_password_login_against_a_google_only_account_is_401(client):
    """Must fail like any wrong password — and must not 500 on the NULL hash."""
    client.post("/auth/google", json={"credential": _token(sub="s-pw", email="pwonly@gmail.com")})
    r = client.post("/auth/login", json={"email": "pwonly@gmail.com", "password": "guessing"})
    assert r.status_code == 401, r.text
