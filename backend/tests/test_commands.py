"""Pending-commands poll: app action enqueues a command the device receives once."""


def test_start_wash_enqueues_command_for_device(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev_headers = {"X-Device-Api-Key": api_key}

    # Nothing queued yet.
    assert client.get("/devices/commands/pending", headers=dev_headers).json() == []

    # App starts a wash → a start_wash command should be enqueued for the device.
    r = client.post("/washing/start", headers=headers, json={"device_id": device_id, "mode": "full_cycle"})
    assert r.status_code == 201, r.text
    cycle_id = r.json()["id"]

    # Device poll returns the command, with the cycle_id in the payload.
    cmds = client.get("/devices/commands/pending", headers=dev_headers).json()
    assert len(cmds) == 1, cmds
    assert cmds[0]["command"] == "start_wash"
    assert cmds[0]["payload"]["cycle_id"] == cycle_id

    # Delivered once — the next poll is empty.
    assert client.get("/devices/commands/pending", headers=dev_headers).json() == []


def test_generic_command_endpoint_enqueues(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev_headers = {"X-Device-Api-Key": api_key}

    r = client.post(f"/devices/{device_id}/command", headers=headers, json={"command": "uv_start"})
    assert r.status_code == 200, r.text

    cmds = client.get("/devices/commands/pending", headers=dev_headers).json()
    assert [c["command"] for c in cmds] == ["uv_start"]


def test_pending_commands_isolated_per_device(client, auth, make_device):
    headers, _ = auth()
    dev1, key1 = make_device(headers)
    dev2, key2 = make_device(headers)

    client.post(f"/devices/{dev1}/command", headers=headers, json={"command": "reboot"})

    # Device 2 must not see device 1's command.
    assert client.get("/devices/commands/pending", headers={"X-Device-Api-Key": key2}).json() == []
    assert len(client.get("/devices/commands/pending", headers={"X-Device-Api-Key": key1}).json()) == 1
