"""device_id is derived from the API key for metrics/activity/alerts;
it's optional in the body but validated (403) when supplied and mismatched."""


def test_metrics_without_device_id_derives_from_key(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev_headers = {"X-Device-Api-Key": api_key}

    # No device_id in the body — derived from the key.
    r = client.post("/metrics/", headers=dev_headers, json={"power_kwh": 0.6, "water_liters": 3})
    assert r.status_code == 201, r.text
    assert r.json()["device_id"] == device_id


def test_activity_without_device_id_derives_from_key(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev_headers = {"X-Device-Api-Key": api_key}

    r = client.post("/activity/", headers=dev_headers, json={"event_type": "device_online"})
    assert r.status_code == 201, r.text
    assert r.json()["device_id"] == device_id


def test_alert_without_device_id_derives_from_key(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev_headers = {"X-Device-Api-Key": api_key}

    r = client.post(
        "/alerts/",
        headers=dev_headers,
        json={"alert_type": "overheating", "message": "Temp too high"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["device_id"] == device_id


def test_mismatched_device_id_still_rejected(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev_headers = {"X-Device-Api-Key": api_key}
    other = device_id + 999  # an id that isn't this key's device

    m = client.post("/metrics/", headers=dev_headers, json={"device_id": other, "power_kwh": 1})
    assert m.status_code == 403, m.text
    a = client.post("/activity/", headers=dev_headers, json={"device_id": other, "event_type": "device_online"})
    assert a.status_code == 403, a.text
    al = client.post("/alerts/", headers=dev_headers, json={"device_id": other, "alert_type": "malfunction", "message": "x"})
    assert al.status_code == 403, al.text


def test_devices_me_returns_own_device(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)

    r = client.get("/devices/me", headers={"X-Device-Api-Key": api_key})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == device_id

    # A bad key is rejected.
    assert client.get("/devices/me", headers={"X-Device-Api-Key": "nope"}).status_code == 403
