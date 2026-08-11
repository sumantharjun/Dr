"""
Multi-baby support: twins on one account.

The behaviour that matters is isolation — one baby's feeds must not move the
other's schedule, totals or alerts. Before this, everything keyed on user_id
alone, so a well-fed twin masked an underfed one.
"""
from datetime import timedelta

from app.utils.timezone import now_ist


def _log(client, headers, baby_id, ml=100, minutes_ago=0, method="manual"):
    return client.post("/feeding/logs", headers=headers, json={
        "baby_id": baby_id,
        "milk_consumed_ml": ml,
        "method": method,
        "milk_type": "formula",
        "feed_time": (now_ist() - timedelta(minutes=minutes_ago)).isoformat(),
    })


# ── multiple profiles ───────────────────────────────────────────────────────

def test_two_babies_can_exist_on_one_account(client, auth, make_baby):
    """The whole point: twins, one account."""
    headers, _ = auth()
    a = make_baby(headers, name="Aarav")
    b = make_baby(headers, name="Ishaan")
    assert a != b
    listed = client.get("/baby/", headers=headers).json()
    assert [x["name"] for x in listed] == ["Aarav", "Ishaan"]


def test_cannot_exceed_the_baby_limit(client, auth, make_baby):
    """Two per account. The UI hides "Add baby" at the limit, but the API is
    what actually enforces it."""
    from app.routers.baby import MAX_BABIES_PER_USER

    assert MAX_BABIES_PER_USER == 2, "frontend MAX_BABIES (store/babyStore.ts) must match"
    headers, _ = auth()
    for _ in range(MAX_BABIES_PER_USER):
        make_baby(headers)
    r = client.post("/baby/", headers=headers, json={
        "name": "Third", "gender": "male", "weight_kg": 4.0,
        "date_of_birth": (now_ist().date() - timedelta(days=30)).isoformat()})
    assert r.status_code == 400, r.text
    assert "2" in r.json()["detail"]
    assert len(client.get("/baby/", headers=headers).json()) == MAX_BABIES_PER_USER


def test_removing_a_baby_frees_a_slot(client, auth, make_baby):
    headers, _ = auth()
    first = make_baby(headers)
    make_baby(headers)
    assert client.delete(f"/baby/{first}", headers=headers).status_code == 204
    # Back under the limit, so another can be added.
    r = client.post("/baby/", headers=headers, json={
        "name": "Replacement", "gender": "female", "weight_kg": 4.0,
        "date_of_birth": (now_ist().date() - timedelta(days=30)).isoformat()})
    assert r.status_code == 201, r.text


def test_baby_list_is_empty_not_404_for_a_new_account(client, auth):
    headers, _ = auth()
    r = client.get("/baby/", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_babies_are_scoped_to_their_account(client, auth, make_baby):
    headers_a, _ = auth()
    baby_a = make_baby(headers_a)
    headers_b, _ = auth()
    assert client.get("/baby/", headers=headers_b).json() == []
    # And another account's baby is invisible, not merely read-only.
    assert client.patch(f"/baby/{baby_a}", headers=headers_b,
                        json={"name": "Hijack"}).status_code == 404
    assert client.delete(f"/baby/{baby_a}", headers=headers_b).status_code == 404


def test_cannot_delete_the_last_baby(client, auth, make_baby):
    headers, _ = auth()
    only = make_baby(headers)
    r = client.delete(f"/baby/{only}", headers=headers)
    assert r.status_code == 400, r.text


def test_deleting_a_baby_keeps_their_feeding_history(client, auth, make_baby):
    """A profile deletion must not silently destroy logged feeds."""
    headers, _ = auth()
    a, b = make_baby(headers, name="A"), make_baby(headers, name="B")
    _log(client, headers, a, ml=120)
    assert client.delete(f"/baby/{a}", headers=headers).status_code == 204

    logs = client.get("/feeding/logs", headers=headers).json()
    assert len(logs) == 1, "the feed should survive"
    assert logs[0]["baby_id"] is None, "and become unattributed, not deleted"


# ── isolation: the actual fix ───────────────────────────────────────────────

def test_one_babys_feed_does_not_move_the_others_schedule(client, auth, make_baby):
    headers, _ = auth()
    a, b = make_baby(headers, name="A"), make_baby(headers, name="B")
    _log(client, headers, a, minutes_ago=5)

    sched_a = client.get(f"/feeding/schedule?baby_id={a}", headers=headers).json()
    sched_b = client.get(f"/feeding/schedule?baby_id={b}", headers=headers).json()
    assert sched_a["last_feed_time"] is not None
    assert sched_b["last_feed_time"] is None, \
        "B has never fed — A's feed must not appear on B's schedule"


def test_analytics_separate_per_baby(client, auth, make_baby):
    headers, _ = auth()
    a, b = make_baby(headers, name="A"), make_baby(headers, name="B")
    _log(client, headers, a, ml=100)
    _log(client, headers, a, ml=50)
    _log(client, headers, b, ml=30)

    tot = lambda bid: sum(  # noqa: E731
        d["total_ml"] for d in
        client.get(f"/feeding/analytics?days=7&baby_id={bid}", headers=headers).json()
    )
    assert tot(a) == 150
    assert tot(b) == 30
    # Unfiltered still spans the account, which is what a single-baby client wants.
    combined = sum(d["total_ml"] for d in
                   client.get("/feeding/analytics?days=7", headers=headers).json())
    assert combined == 180


def test_logs_filter_by_baby(client, auth, make_baby):
    headers, _ = auth()
    a, b = make_baby(headers, name="A"), make_baby(headers, name="B")
    _log(client, headers, a)
    _log(client, headers, b)
    _log(client, headers, b)
    assert len(client.get(f"/feeding/logs?baby_id={a}", headers=headers).json()) == 1
    assert len(client.get(f"/feeding/logs?baby_id={b}", headers=headers).json()) == 2
    assert len(client.get("/feeding/logs", headers=headers).json()) == 3


def test_underfed_twin_is_not_masked_by_a_well_fed_one(client, auth, make_device, make_baby):
    """
    The regression this whole change exists for.

    Alerts used to be computed across the account, so a recently-fed twin kept
    the pooled "last feed" fresh and the overdue sibling never triggered one.
    """
    headers, _ = auth()
    device_id, _ = make_device(headers)
    hungry, fed = make_baby(headers, name="Hungry"), make_baby(headers, name="Fed")

    # Hungry last ate 8 hours ago; Fed ate a minute ago.
    client.post("/feeding/logs", headers=headers, json={
        "baby_id": hungry, "device_id": device_id, "milk_consumed_ml": 100,
        "method": "manual", "milk_type": "formula",
        "feed_time": (now_ist() - timedelta(hours=8)).isoformat()})
    client.post("/feeding/logs", headers=headers, json={
        "baby_id": fed, "device_id": device_id, "milk_consumed_ml": 100,
        "method": "manual", "milk_type": "formula",
        "feed_time": now_ist().isoformat()})

    # Logging anything for Hungry re-evaluates only Hungry's rules.
    client.post("/feeding/logs", headers=headers, json={
        "baby_id": hungry, "device_id": device_id, "milk_consumed_ml": 100,
        "method": "manual", "milk_type": "formula",
        "feed_time": (now_ist() - timedelta(hours=8)).isoformat()})

    alerts = client.get("/alerts/", headers=headers).json()
    overdue = [a for a in alerts if a["alert_type"] == "overdue_feed"]
    assert overdue, "an overdue alert should fire for the twin who hasn't fed"
    assert "Hungry" in overdue[0]["message"], \
        f"the alert must name which twin: {overdue[0]['message']}"


def test_alert_type_stays_a_plain_catalog_key(client, auth, make_device, make_baby):
    """The frontend's alertMeta() and alerts_catalog.py look this up exactly —
    encoding the baby id into it would break every label and icon."""
    headers, _ = auth()
    device_id, _ = make_device(headers)
    baby = make_baby(headers, name="Solo")
    client.post("/feeding/logs", headers=headers, json={
        "baby_id": baby, "device_id": device_id, "milk_consumed_ml": 100,
        "method": "manual", "milk_type": "formula",
        "feed_time": (now_ist() - timedelta(hours=8)).isoformat()})
    for a in client.get("/alerts/", headers=headers).json():
        assert ":" not in a["alert_type"], f"unexpected suffix: {a['alert_type']}"


# ── attribution and ownership ───────────────────────────────────────────────

def test_feeding_log_requires_a_baby(client, auth, make_baby):
    headers, _ = auth()
    make_baby(headers)
    r = client.post("/feeding/logs", headers=headers, json={
        "milk_consumed_ml": 100, "method": "manual", "milk_type": "formula"})
    assert r.status_code == 422, r.text


def test_cannot_log_a_feed_against_someone_elses_baby(client, auth, make_baby):
    headers_a, _ = auth()
    baby_a = make_baby(headers_a)
    headers_b, _ = auth()
    make_baby(headers_b)
    r = _log(client, headers_b, baby_a)
    assert r.status_code == 404, r.text


def test_filtering_by_someone_elses_baby_is_404(client, auth, make_baby):
    headers_a, _ = auth()
    baby_a = make_baby(headers_a)
    headers_b, _ = auth()
    for path in (f"/feeding/logs?baby_id={baby_a}",
                 f"/feeding/analytics?baby_id={baby_a}",
                 f"/feeding/schedule?baby_id={baby_a}"):
        assert client.get(path, headers=headers_b).status_code == 404, path


# ── "feeding now" and device reports ────────────────────────────────────────

def test_device_report_is_unattributed_until_a_baby_is_selected(client, auth,
                                                                make_device, make_baby):
    """Guessing would be worse than leaving it blank."""
    headers, _ = auth()
    _, api_key = make_device(headers)
    make_baby(headers)
    r = client.post("/feeding/device-report", headers={"X-Device-Api-Key": api_key},
                    json={"weight_before_g": 320.0, "weight_after_g": 190.0})
    assert r.status_code == 201, r.text
    assert r.json()["baby_id"] is None


def test_device_report_follows_the_active_baby(client, auth, make_device, make_baby):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    a, b = make_baby(headers, name="A"), make_baby(headers, name="B")

    assert client.patch(f"/devices/{device_id}/active-baby", headers=headers,
                        json={"baby_id": b}).status_code == 200
    r = client.post("/feeding/device-report", headers={"X-Device-Api-Key": api_key},
                    json={"weight_before_g": 320.0, "weight_after_g": 190.0})
    assert r.json()["baby_id"] == b

    # Switching re-targets subsequent reports.
    client.patch(f"/devices/{device_id}/active-baby", headers=headers, json={"baby_id": a})
    r2 = client.post("/feeding/device-report", headers={"X-Device-Api-Key": api_key},
                     json={"weight_before_g": 300.0, "weight_after_g": 200.0})
    assert r2.json()["baby_id"] == a


def test_active_baby_can_be_cleared(client, auth, make_device, make_baby):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    a = make_baby(headers)
    client.patch(f"/devices/{device_id}/active-baby", headers=headers, json={"baby_id": a})
    client.patch(f"/devices/{device_id}/active-baby", headers=headers, json={"baby_id": None})
    r = client.post("/feeding/device-report", headers={"X-Device-Api-Key": api_key},
                    json={"weight_before_g": 320.0, "weight_after_g": 190.0})
    assert r.json()["baby_id"] is None, "cleared means unattributed, not last-used"


def test_cannot_set_another_accounts_baby_as_active(client, auth, make_device, make_baby):
    headers_a, _ = auth()
    baby_a = make_baby(headers_a)
    headers_b, _ = auth()
    device_b, _ = make_device(headers_b)
    r = client.patch(f"/devices/{device_b}/active-baby", headers=headers_b,
                     json={"baby_id": baby_a})
    assert r.status_code == 404, r.text


def test_deleting_the_active_baby_clears_the_pointer(client, auth, make_device, make_baby):
    """Otherwise the FK blocks the delete outright."""
    headers, _ = auth()
    device_id, _ = make_device(headers)
    a, b = make_baby(headers, name="A"), make_baby(headers, name="B")
    client.patch(f"/devices/{device_id}/active-baby", headers=headers, json={"baby_id": a})
    assert client.delete(f"/baby/{a}", headers=headers).status_code == 204
    devices = client.get("/devices/", headers=headers).json()
    assert devices[0]["active_baby_id"] is None
