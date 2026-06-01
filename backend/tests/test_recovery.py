"""End-to-end tests for the stuck-cycle recovery work (BUG-1/2/3, F-fixes)."""


def _start_wash(client, headers, device_id, mode="full_cycle", force=False):
    return client.post(
        "/washing/start",
        headers=headers,
        json={"device_id": device_id, "mode": mode, "force": force},
    )


def test_double_start_conflicts_then_force_supersedes(client, auth, make_device):
    headers, _ = auth()
    device_id, _ = make_device(headers)

    r1 = _start_wash(client, headers, device_id)
    assert r1.status_code == 201, r1.text

    # Second start while one is active → 409 with the active cycle surfaced.
    r2 = _start_wash(client, headers, device_id)
    assert r2.status_code == 409
    assert r2.json()["active_cycle_id"] == r1.json()["id"]

    # force=true supersedes the stuck one and creates a fresh cycle.
    r3 = _start_wash(client, headers, device_id, force=True)
    assert r3.status_code == 201
    assert r3.json()["id"] != r1.json()["id"]


def test_terminal_guard_blocks_resurrection(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev_headers = {"X-Device-Api-Key": api_key}

    cycle_id = _start_wash(client, headers, device_id).json()["id"]

    # Device reports completion.
    r = client.post(
        "/washing/progress",
        headers=dev_headers,
        json={"cycle_id": cycle_id, "status": "completed", "progress_pct": 100},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # A duplicate completion packet is an idempotent no-op (200).
    r = client.post(
        "/washing/progress",
        headers=dev_headers,
        json={"cycle_id": cycle_id, "status": "completed", "progress_pct": 100},
    )
    assert r.status_code == 200

    # A contradicting late packet cannot revive the terminal cycle → 409.
    r = client.post(
        "/washing/progress",
        headers=dev_headers,
        json={"cycle_id": cycle_id, "status": "running", "progress_pct": 50},
    )
    assert r.status_code == 409, r.text


def test_cancel_resets_stuck_cycle(client, auth, make_device):
    headers, _ = auth()
    device_id, _ = make_device(headers)
    cycle_id = _start_wash(client, headers, device_id).json()["id"]

    r = client.patch(f"/washing/{cycle_id}/cancel", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "failed"
    assert body["ended_reason"] == "cancelled"

    # With the cycle cleared, a brand-new wash can start without force.
    assert _start_wash(client, headers, device_id).status_code == 201
