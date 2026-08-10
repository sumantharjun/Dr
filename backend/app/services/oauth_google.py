"""
Verification of Google Sign-In ID tokens.

The browser receives a signed ID token (a JWT) from Google Identity Services and
posts it to us. Our job is to prove that token really came from Google, really
names our app, and really asserts a verified email — then never use it again.
Everything afterwards runs on the app's own session token.

Google's signing keys are fetched from its JWKS endpoint and cached in-process,
using stdlib urllib to match utils/email.py and services/exchange_rates.py —
requirements.txt deliberately carries no HTTP client. Signature verification uses
python-jose, already a dependency.

No client secret is involved anywhere: verifying an ID token needs only public
keys, which is the whole appeal of this flow.
"""
import json
import logging
import time
import urllib.request
from typing import Optional

from jose import jwt
from jose.exceptions import JWTError

from app.config import settings

logger = logging.getLogger(__name__)

CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
# Google documents both spellings; tokens carry one or the other.
VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

# Google rotates signing keys roughly daily and the endpoint sends cache headers
# well above this, so an hour is conservative.
JWKS_TTL_SECONDS = 60 * 60
FETCH_TIMEOUT_SECONDS = 8

_jwks_cache: Optional[tuple[dict, float]] = None


class GoogleAuthError(Exception):
    """Raised for any token we will not accept. The router turns this into a 401
    — never a 500, since a bad token is a client problem, not a server fault."""


def _fetch_jwks() -> dict:
    req = urllib.request.Request(
        CERTS_URL, headers={"User-Agent": "unova-backend/1.0"}, method="GET"
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode())


def get_jwks(force_refresh: bool = False) -> dict:
    """Google's public signing keys, cached. `force_refresh` bypasses the cache
    once, so an unrecognised `kid` (a key rotation) can be retried rather than
    failing every login until the TTL lapses."""
    global _jwks_cache
    now = time.time()
    if not force_refresh and _jwks_cache is not None:
        jwks, fetched_at = _jwks_cache
        if now - fetched_at < JWKS_TTL_SECONDS:
            return jwks
    jwks = _fetch_jwks()
    _jwks_cache = (jwks, now)
    return jwks


def reset_cache() -> None:
    """Clear the cached keys. For tests."""
    global _jwks_cache
    _jwks_cache = None


def _key_for(kid: Optional[str]) -> dict:
    for refresh in (False, True):
        for key in get_jwks(force_refresh=refresh).get("keys", []):
            if key.get("kid") == kid:
                return key
        # Miss on the cached copy → refetch once in case Google rotated keys.
    raise GoogleAuthError("Token signed with an unrecognised key")


def verify_id_token(credential: str) -> dict:
    """
    Validate a Google ID token and return its claims.

    Raises GoogleAuthError on anything suspect. Checks, in order: a configured
    audience, the signing key, the signature + `aud` + `iss` + `exp` (jose does
    these together), a subject, and finally that Google says the email is
    verified.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleAuthError("Google Sign-In is not configured on this server")

    try:
        header = jwt.get_unverified_header(credential)
    except JWTError as exc:
        raise GoogleAuthError("Malformed token") from exc

    key = _key_for(header.get("kid"))

    try:
        claims = jwt.decode(
            credential,
            key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        # Covers a bad signature, wrong audience and expiry alike. The message
        # is deliberately vague to the caller; the detail goes to the log.
        logger.warning("Rejected Google ID token: %s", exc)
        raise GoogleAuthError("Invalid or expired Google token") from exc

    if claims.get("iss") not in VALID_ISSUERS:
        raise GoogleAuthError("Unexpected token issuer")

    if not claims.get("sub"):
        raise GoogleAuthError("Token is missing a subject")

    email = claims.get("email")
    if not email:
        raise GoogleAuthError("Google did not provide an email address")

    # The takeover guard. Without this, anyone able to mint a Google account
    # with an unverified address could claim an existing password account that
    # happens to use it.
    if claims.get("email_verified") is not True:
        raise GoogleAuthError("Google has not verified this email address")

    return claims
