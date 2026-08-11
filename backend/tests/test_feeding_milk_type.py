"""Tests for the required `milk_type` field on feeding logs."""

import pytest


def test_milk_type_is_required(client, auth, make_baby):
    headers, _ = auth()
    baby_id = make_baby(headers)
    r = client.post(
        "/feeding/logs",
        headers=headers,
        json={"baby_id": baby_id, "milk_consumed_ml": 100, "method": "manual"},
    )
    assert r.status_code == 422, r.text


@pytest.mark.parametrize(
    "milk_type", ["breast_milk", "formula", "cow_milk", "mixed", "other"]
)
def test_all_milk_types_accepted_and_round_trip(client, auth, make_baby, milk_type):
    headers, _ = auth()
    baby_id = make_baby(headers)
    r = client.post(
        "/feeding/logs",
        headers=headers,
        json={"baby_id": baby_id, "milk_consumed_ml": 100, "method": "manual", "milk_type": milk_type},
    )
    assert r.status_code == 201, r.text
    assert r.json()["milk_type"] == milk_type

    # It must survive the read path too, not just the create response.
    logs = client.get("/feeding/logs", headers=headers).json()
    assert logs[0]["milk_type"] == milk_type


def test_unknown_milk_type_rejected(client, auth, make_baby):
    headers, _ = auth()
    baby_id = make_baby(headers)
    r = client.post(
        "/feeding/logs",
        headers=headers,
        json={"baby_id": baby_id, "milk_consumed_ml": 100, "method": "manual", "milk_type": "goat_milk"},
    )
    assert r.status_code == 422, r.text


def test_device_report_omits_milk_type(client, auth, make_device, make_baby):
    """The scale can't know what's in the bottle, so the field stays optional
    there and the log is left untyped rather than guessed."""
    headers, _ = auth()
    baby_id = make_baby(headers)
    _, api_key = make_device(headers)
    r = client.post(
        "/feeding/device-report",
        headers={"X-Device-Api-Key": api_key},
        json={"weight_before_g": 320.0, "weight_after_g": 190.0},
    )
    assert r.status_code == 201, r.text
    assert r.json()["milk_type"] is None


def test_device_report_accepts_milk_type(client, auth, make_device, make_baby):
    headers, _ = auth()
    baby_id = make_baby(headers)
    _, api_key = make_device(headers)
    r = client.post(
        "/feeding/device-report",
        headers={"X-Device-Api-Key": api_key},
        json={
            "weight_before_g": 320.0,
            "weight_after_g": 190.0,
            "milk_type": "formula",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["milk_type"] == "formula"


def test_device_report_rejects_bad_milk_type(client, auth, make_device, make_baby):
    headers, _ = auth()
    baby_id = make_baby(headers)
    _, api_key = make_device(headers)
    r = client.post(
        "/feeding/device-report",
        headers={"X-Device-Api-Key": api_key},
        json={
            "weight_before_g": 320.0,
            "weight_after_g": 190.0,
            "milk_type": "not_a_type",
        },
    )
    assert r.status_code == 422, r.text
