"""Tests for the baby date-of-birth field and derived age."""
from datetime import timedelta

import pytest

from app.utils.timezone import now_ist


def _auth(client, auth):
    headers, _ = auth()
    return headers


def _iso(days_ago: int) -> str:
    return (now_ist().date() - timedelta(days=days_ago)).isoformat()


def _create(client, headers, **overrides):
    body = {"name": "Ari", "gender": "female", "weight_kg": 4.2, "date_of_birth": _iso(60)}
    body.update(overrides)
    return client.post("/baby/", headers=headers, json=body)


# ── create ──────────────────────────────────────────────────────────────────

def test_date_of_birth_is_required_on_create(client, auth):
    headers = _auth(client, auth)
    r = client.post(
        "/baby/",
        headers=headers,
        json={"name": "Ari", "gender": "female", "weight_kg": 4.2},
    )
    assert r.status_code == 422, r.text


def test_create_stores_dob_and_derives_age(client, auth):
    headers = _auth(client, auth)
    r = _create(client, headers, date_of_birth=_iso(60))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["date_of_birth"] == _iso(60)
    assert body["age_days"] == 60


def test_born_today_is_zero_days_not_null(client, auth):
    """0 must round-trip as 0 — a falsy age must not read as 'unknown'."""
    headers = _auth(client, auth)
    r = _create(client, headers, date_of_birth=_iso(0))
    assert r.status_code == 201, r.text
    assert r.json()["age_days"] == 0


@pytest.mark.parametrize("days_ago", [-1, -30])
def test_future_dob_rejected(client, auth, days_ago):
    headers = _auth(client, auth)
    r = _create(client, headers, date_of_birth=_iso(days_ago))
    assert r.status_code == 422, r.text


def test_implausibly_old_dob_rejected(client, auth):
    """Catches the common mistyped-year error."""
    headers = _auth(client, auth)
    r = _create(client, headers, date_of_birth=_iso(365 * 11))
    assert r.status_code == 422, r.text


def test_dob_at_the_boundary_is_accepted(client, auth):
    headers = _auth(client, auth)
    r = _create(client, headers, date_of_birth=_iso(365 * 9))
    assert r.status_code == 201, r.text


def test_malformed_dob_rejected(client, auth):
    headers = _auth(client, auth)
    r = _create(client, headers, date_of_birth="not-a-date")
    assert r.status_code == 422, r.text


# ── read ────────────────────────────────────────────────────────────────────

def test_get_returns_dob_and_age(client, auth):
    headers = _auth(client, auth)
    _create(client, headers, date_of_birth=_iso(200))
    r = client.get("/baby/", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()[0]["date_of_birth"] == _iso(200)
    assert r.json()[0]["age_days"] == 200


def test_legacy_profile_without_dob_reports_null_age(client, auth):
    """Profiles created before this field existed must still serialise, with
    age_days null rather than 0 or an error."""
    from app.database import SessionLocal
    from app.models.baby import Baby
    from app.models.user import User

    headers = _auth(client, auth)
    db = SessionLocal()
    try:
        user_id = db.query(User).order_by(User.id.desc()).first().id
        db.add(Baby(user_id=user_id, name="Legacy", gender="male",
                    weight_kg=5.0, theme_color="blue", date_of_birth=None))
        db.commit()
    finally:
        db.close()

    r = client.get("/baby/", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()[0]["date_of_birth"] is None
    assert r.json()[0]["age_days"] is None


# ── update ──────────────────────────────────────────────────────────────────

def test_patch_can_backfill_a_missing_dob(client, auth):
    """The path an existing parent takes from Settings."""
    from app.database import SessionLocal
    from app.models.baby import Baby
    from app.models.user import User

    headers = _auth(client, auth)
    db = SessionLocal()
    try:
        user_id = db.query(User).order_by(User.id.desc()).first().id
        db.add(Baby(user_id=user_id, name="Legacy", gender="male",
                    weight_kg=5.0, theme_color="blue", date_of_birth=None))
        db.commit()
    finally:
        db.close()

    baby_id = client.get("/baby/", headers=headers).json()[0]["id"]
    r = client.patch(f"/baby/{baby_id}", headers=headers, json={"date_of_birth": _iso(90)})
    assert r.status_code == 200, r.text
    assert r.json()["date_of_birth"] == _iso(90)
    assert r.json()["age_days"] == 90


def test_patch_without_dob_leaves_it_untouched(client, auth):
    headers = _auth(client, auth)
    baby_id = _create(client, headers, date_of_birth=_iso(45)).json()["id"]
    r = client.patch(f"/baby/{baby_id}", headers=headers, json={"weight_kg": 6.1})
    assert r.status_code == 200, r.text
    assert r.json()["date_of_birth"] == _iso(45), "DOB must survive an unrelated update"
    assert r.json()["weight_kg"] == 6.1


def test_patch_rejects_a_future_dob(client, auth):
    headers = _auth(client, auth)
    baby_id = _create(client, headers, date_of_birth=_iso(45)).json()["id"]
    r = client.patch(f"/baby/{baby_id}", headers=headers, json={"date_of_birth": _iso(-1)})
    assert r.status_code == 422, r.text
