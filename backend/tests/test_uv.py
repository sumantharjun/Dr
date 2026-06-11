"""UV sterilization domain: start, status reporting, recovery, history, authz."""


def _start(client, headers, device_id, force=False):
    return client.post("/uv/start", headers=headers, json={"device_id": device_id, "force": force})


def test_uv_start_and_report_completed(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev = {"X-Device-Api-Key": api_key}

    r = _start(client, headers, device_id)
    assert r.status_code == 201, r.text
    uv_id = r.json()["id"]
    assert r.json()["status"] == "started"

    # A start_wash-style command is queued with the uv_cycle_id.
    cmds = client.get("/devices/commands/pending", headers=dev).json()
    assert any(c["command"] == "uv_start" and c["payload"].get("uv_cycle_id") == uv_id for c in cmds)

    # Device reports completion.
    r = client.post("/uv/progress", headers=dev, json={"uv_cycle_id": uv_id, "status": "completed"})
    assert r.status_code == 200
    assert r.json()["status"] == "completed" and r.json()["ended_reason"] == "completed"


def test_uv_terminal_guard(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev = {"X-Device-Api-Key": api_key}
    uv_id = _start(client, headers, device_id).json()["id"]

    assert client.post("/uv/progress", headers=dev, json={"uv_cycle_id": uv_id, "status": "failed"}).status_code == 200
    # Idempotent repeat of the same terminal status is accepted.
    assert client.post("/uv/progress", headers=dev, json={"uv_cycle_id": uv_id, "status": "failed"}).status_code == 200
    # A contradicting transition on a terminal cycle is rejected.
    assert client.post("/uv/progress", headers=dev, json={"uv_cycle_id": uv_id, "status": "completed"}).status_code == 409


def test_uv_double_start_then_force(client, auth, make_device):
    headers, _ = auth()
    device_id, _ = make_device(headers)
    first = _start(client, headers, device_id).json()["id"]
    r2 = _start(client, headers, device_id)
    assert r2.status_code == 409 and r2.json()["active_uv_cycle_id"] == first
    r3 = _start(client, headers, device_id, force=True)
    assert r3.status_code == 201 and r3.json()["id"] != first


def test_uv_device_start(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    r = client.post("/uv/device-start", headers={"X-Device-Api-Key": api_key}, json={})
    assert r.status_code == 201
    assert r.json()["initiated_by"] == "device" and r.json()["status"] == "started"


def test_uv_cancel_then_restart(client, auth, make_device):
    headers, _ = auth()
    device_id, _ = make_device(headers)
    uv_id = _start(client, headers, device_id).json()["id"]

    r = client.patch(f"/uv/{uv_id}/cancel", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "failed" and r.json()["ended_reason"] == "cancelled"
    # With the cycle cleared, a new UV cycle can start without force.
    assert _start(client, headers, device_id).status_code == 201


def test_uv_history_and_cross_user_isolation(client, auth, make_device):
    headers_a, _ = auth()
    device_a, _ = make_device(headers_a)
    _start(client, headers_a, device_a)

    # History is scoped to the owner.
    assert len(client.get("/uv/history", headers=headers_a).json()) == 1
    headers_b, _ = auth()
    assert client.get("/uv/history", headers=headers_b).json() == []
    # User B can't start UV on A's device.
    assert _start(client, headers_b, device_a).status_code == 404
