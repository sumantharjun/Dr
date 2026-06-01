"""Regression tests for the feeding IDOR fix (POST /feeding/logs)."""


def test_cannot_log_feed_for_another_users_device(client, auth, make_device):
    # User A owns a device.
    headers_a, _ = auth()
    device_a_id, _ = make_device(headers_a)

    # User B tries to attach a feeding log to user A's device → must be rejected.
    headers_b, _ = auth()
    r = client.post(
        "/feeding/logs",
        headers=headers_b,
        json={"device_id": device_a_id, "milk_consumed_ml": 100, "method": "device"},
    )
    assert r.status_code == 404, r.text


def test_can_log_feed_for_own_device(client, auth, make_device):
    headers, _ = auth()
    device_id, _ = make_device(headers)
    r = client.post(
        "/feeding/logs",
        headers=headers,
        json={"device_id": device_id, "milk_consumed_ml": 120, "method": "device"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["device_id"] == device_id


def test_manual_feed_without_device_allowed(client, auth):
    headers, _ = auth()
    r = client.post(
        "/feeding/logs",
        headers=headers,
        json={"milk_consumed_ml": 90, "method": "manual"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["device_id"] is None
