"""Tests for the account-level app theme (users.theme_color)."""
import pytest

from app.schemas.user import VALID_THEME_COLORS

THEMES = sorted(VALID_THEME_COLORS)


def _auth(client, auth):
    headers, _ = auth()
    return headers


def test_new_user_defaults_to_pastel_green(client, auth):
    """The client asked for green as the starting colour."""
    headers, _ = auth()
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["theme_color"] == "green"


def test_theme_is_returned_on_register_and_login(client):
    """Sign-in responses carry the colour so a new device paints correctly."""
    reg = client.post("/auth/register", json={
        "email": "theme1@test.com", "full_name": "T", "password": "Sup3rSecret!"})
    assert reg.status_code == 201, reg.text
    assert reg.json()["user"]["theme_color"] == "green"

    login = client.post("/auth/login", json={
        "email": "theme1@test.com", "password": "Sup3rSecret!"})
    assert login.json()["user"]["theme_color"] == "green"


@pytest.mark.parametrize("theme", THEMES)
def test_every_palette_can_be_selected(client, auth, theme):
    headers = _auth(client, auth)
    r = client.patch("/auth/me/preferences", headers=headers, json={"theme_color": theme})
    assert r.status_code == 200, r.text
    assert r.json()["theme_color"] == theme
    # And it must survive the read path, not just echo back.
    assert client.get("/auth/me", headers=headers).json()["theme_color"] == theme


def test_unknown_theme_rejected(client, auth):
    headers = _auth(client, auth)
    r = client.patch("/auth/me/preferences", headers=headers, json={"theme_color": "chartreuse"})
    assert r.status_code == 422, r.text


def test_old_gender_derived_values_are_still_valid(client, auth):
    """blue and pink are kept so existing users' colours survive the migration."""
    headers = _auth(client, auth)
    for theme in ("blue", "pink"):
        assert client.patch("/auth/me/preferences", headers=headers,
                            json={"theme_color": theme}).status_code == 200


def test_omitted_field_leaves_theme_unchanged(client, auth):
    headers = _auth(client, auth)
    client.patch("/auth/me/preferences", headers=headers, json={"theme_color": "lilac"})
    r = client.patch("/auth/me/preferences", headers=headers, json={})
    assert r.status_code == 200, r.text
    assert r.json()["theme_color"] == "lilac"


def test_preferences_requires_auth(client):
    assert client.patch("/auth/me/preferences", json={"theme_color": "blue"}).status_code == 403


def test_theme_is_per_account_not_shared(client, auth):
    a, _ = auth()
    b, _ = auth()
    client.patch("/auth/me/preferences", headers=a, json={"theme_color": "peach"})
    assert client.get("/auth/me", headers=a).json()["theme_color"] == "peach"
    assert client.get("/auth/me", headers=b).json()["theme_color"] == "green", \
        "one account's colour must not leak to another"


# ── the baby no longer carries a colour ─────────────────────────────────────

def test_baby_create_ignores_a_theme_color(client, auth):
    """Colour is no longer a baby attribute; sending one must not 500 or persist."""
    from datetime import timedelta
    from app.utils.timezone import now_ist

    headers = _auth(client, auth)
    r = client.post("/baby/", headers=headers, json={
        "name": "Ari", "gender": "female", "weight_kg": 4.2,
        "date_of_birth": (now_ist().date() - timedelta(days=30)).isoformat(),
        "theme_color": "pink",  # extra field from an older client
    })
    assert r.status_code == 201, r.text
    assert "theme_color" not in r.json(), "baby responses should no longer expose a colour"


def test_baby_gender_no_longer_sets_a_theme(client, auth):
    """A boy profile used to force blue. The account colour must be untouched."""
    from datetime import timedelta
    from app.utils.timezone import now_ist

    headers = _auth(client, auth)
    client.patch("/auth/me/preferences", headers=headers, json={"theme_color": "slate"})
    client.post("/baby/", headers=headers, json={
        "name": "Boy", "gender": "male", "weight_kg": 4.0,
        "date_of_birth": (now_ist().date() - timedelta(days=30)).isoformat()})
    assert client.get("/auth/me", headers=headers).json()["theme_color"] == "slate"
