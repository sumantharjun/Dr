"""Tests for the required baby name."""
from datetime import timedelta

import pytest

from app.utils.timezone import now_ist


def _dob() -> str:
    return (now_ist().date() - timedelta(days=60)).isoformat()


def _body(**overrides):
    body = {"name": "Ari", "gender": "female", "weight_kg": 4.2, "date_of_birth": _dob()}
    body.update(overrides)
    return body


# ── create ──────────────────────────────────────────────────────────────────

def test_name_is_required_on_create(client, auth):
    headers, _ = auth()
    body = _body()
    del body["name"]
    r = client.post("/baby/", headers=headers, json=body)
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n  "])
def test_blank_name_rejected(client, auth, blank):
    """Whitespace must not slip past the requirement."""
    headers, _ = auth()
    r = client.post("/baby/", headers=headers, json=_body(name=blank))
    assert r.status_code == 422, r.text


def test_explicit_null_name_rejected(client, auth):
    headers, _ = auth()
    r = client.post("/baby/", headers=headers, json=_body(name=None))
    assert r.status_code == 422, r.text


def test_name_is_trimmed_on_save(client, auth):
    headers, _ = auth()
    r = client.post("/baby/", headers=headers, json=_body(name="  Aarav  "))
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Aarav", "surrounding whitespace should not be stored"


def test_overlong_name_rejected(client, auth):
    headers, _ = auth()
    r = client.post("/baby/", headers=headers, json=_body(name="x" * 256))
    assert r.status_code == 422, r.text


def test_name_at_max_length_accepted(client, auth):
    headers, _ = auth()
    r = client.post("/baby/", headers=headers, json=_body(name="x" * 255))
    assert r.status_code == 201, r.text


# ── update ──────────────────────────────────────────────────────────────────

def test_patch_cannot_blank_an_existing_name(client, auth):
    """The whole point of the change — a name, once set, can't be removed."""
    headers, _ = auth()
    baby_id = client.post("/baby/", headers=headers, json=_body(name="Aarav")).json()["id"]
    r = client.patch(f"/baby/{baby_id}", headers=headers, json={"name": "   "})
    assert r.status_code == 422, r.text
    assert client.get("/baby/", headers=headers).json()[0]["name"] == "Aarav"


def test_patch_can_rename(client, auth):
    headers, _ = auth()
    baby_id = client.post("/baby/", headers=headers, json=_body(name="Aarav")).json()["id"]
    r = client.patch(f"/baby/{baby_id}", headers=headers, json={"name": "  Ishaan "})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Ishaan"


def test_patch_omitting_name_leaves_it_alone(client, auth):
    headers, _ = auth()
    baby_id = client.post("/baby/", headers=headers, json=_body(name="Aarav")).json()["id"]
    r = client.patch(f"/baby/{baby_id}", headers=headers, json={"weight_kg": 5.5})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Aarav"
    assert r.json()["weight_kg"] == 5.5


def test_get_always_returns_a_name(client, auth):
    headers, _ = auth()
    client.post("/baby/", headers=headers, json=_body(name="Aarav"))
    body = client.get("/baby/", headers=headers).json()[0]
    assert isinstance(body["name"], str) and body["name"].strip()
