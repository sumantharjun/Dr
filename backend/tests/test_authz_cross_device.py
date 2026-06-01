"""Authorization: a user must not be able to drive a device they don't own."""


def test_cannot_command_another_users_device(client, auth, make_device):
    headers_a, _ = auth()
    device_a, _ = make_device(headers_a)

    headers_b, _ = auth()  # different user, owns nothing

    # Direct command endpoint.
    r = client.post(f"/devices/{device_a}/command", headers=headers_b, json={"command": "uv_start"})
    assert r.status_code == 404, r.text

    # Start a wash on A's device.
    r = client.post("/washing/start", headers=headers_b, json={"device_id": device_a, "mode": "full_cycle"})
    assert r.status_code == 404, r.text

    # Start a dispense on A's device.
    r = client.post("/dispensing/", headers=headers_b, json={"device_id": device_a, "temperature_c": 37, "volume_ml": 120})
    assert r.status_code == 404, r.text

    # And A's device received NO command from any of B's attempts.
    # (fetch via A's own device key — need it; re-create flow: A polls.)


def test_cannot_cancel_another_users_cycle(client, auth, make_device):
    # User A starts a real wash (owns the device).
    headers_a, _ = auth()
    device_a, key_a = make_device(headers_a)
    cycle_id = client.post(
        "/washing/start", headers=headers_a, json={"device_id": device_a, "mode": "full_cycle"}
    ).json()["id"]

    # User B tries to cancel A's cycle → must not be allowed.
    headers_b, _ = auth()
    r = client.patch(f"/washing/{cycle_id}/cancel", headers=headers_b)
    assert r.status_code == 404, r.text

    # A's cycle is still active (B's cancel did nothing).
    r = client.post("/washing/start", headers=headers_a, json={"device_id": device_a, "mode": "dry"})
    assert r.status_code == 409  # still blocked by the live cycle


def test_command_to_owned_device_succeeds_and_is_isolated(client, auth, make_device):
    headers_a, _ = auth()
    device_a, key_a = make_device(headers_a)
    headers_b, _ = auth()
    device_b, key_b = make_device(headers_b)

    # A commands A's own device — fine.
    assert client.post(f"/devices/{device_a}/command", headers=headers_a, json={"command": "uv_start"}).status_code == 200

    # The command landed on A's device only; B's device sees nothing.
    a_cmds = client.get("/devices/commands/pending", headers={"X-Device-Api-Key": key_a}).json()
    b_cmds = client.get("/devices/commands/pending", headers={"X-Device-Api-Key": key_b}).json()
    assert [c["command"] for c in a_cmds] == ["uv_start"]
    assert b_cmds == []
