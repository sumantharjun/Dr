"""Tests for the firmware-spec changes: modes, scoop_number, uv_start, metrics."""


def test_removed_wash_modes_rejected(client, auth, make_device):
    headers, _ = auth()
    device_id, _ = make_device(headers)
    for mode in ("wash", "deep_clean", "dispense"):
        r = client.post(
            "/washing/start",
            headers=headers,
            json={"device_id": device_id, "mode": mode},
        )
        assert r.status_code == 400, f"{mode} should be rejected, got {r.status_code}"


def test_allowed_wash_modes_accepted(client, auth, make_device):
    headers, _ = auth()
    for mode in ("full_cycle", "steam_dry", "dry"):
        device_id, _ = make_device(headers)  # fresh device so no active-cycle conflict
        r = client.post(
            "/washing/start",
            headers=headers,
            json={"device_id": device_id, "mode": mode},
        )
        assert r.status_code == 201, f"{mode} should be accepted: {r.text}"


def test_dispense_accepts_scoop_number(client, auth, make_device):
    headers, _ = auth()
    device_id, _ = make_device(headers)
    r = client.post(
        "/dispensing/",
        headers=headers,
        json={"device_id": device_id, "temperature_c": 37, "volume_ml": 120, "scoop_number": 2},
    )
    assert r.status_code == 201, r.text
    assert r.json()["scoop_number"] == 2


def test_dispense_scoop_out_of_range_rejected(client, auth, make_device):
    headers, _ = auth()
    device_id, _ = make_device(headers)
    r = client.post(
        "/dispensing/",
        headers=headers,
        json={"device_id": device_id, "temperature_c": 37, "volume_ml": 120, "scoop_number": 99},
    )
    assert r.status_code == 422


def test_uv_start_command_accepted(client, auth, make_device):
    headers, _ = auth()
    device_id, _ = make_device(headers)
    r = client.post(f"/devices/{device_id}/command", headers=headers, json={"command": "uv_start"})
    assert r.status_code == 200, r.text


def test_metrics_summary_estimates_from_completed_cycles(client, auth, make_device):
    headers, _ = auth()
    device_id, api_key = make_device(headers)
    dev_headers = {"X-Device-Api-Key": api_key}

    # Baseline: no completed cycles → no savings.
    base = client.get("/metrics/summary", headers=headers).json()
    assert base["total_cycles"] == 0
    assert base["power_saved_kwh"] == 0

    # Complete one wash cycle.
    cycle_id = client.post(
        "/washing/start", headers=headers, json={"device_id": device_id, "mode": "full_cycle"}
    ).json()["id"]
    client.post(
        "/washing/progress",
        headers=dev_headers,
        json={"cycle_id": cycle_id, "status": "completed", "progress_pct": 100},
    )

    summary = client.get("/metrics/summary", headers=headers).json()
    assert summary["total_cycles"] == 1
    assert summary["power_saved_kwh"] > 0  # estimated from cycle count, no meters
    assert summary["water_saved_liters"] > 0
