"""Tests for the shop's currency conversion rates (GET /orders/rates).

The network is never touched here: `_fetch` is monkeypatched in every test, so
the suite stays offline and deterministic.
"""
import pytest

from app.services import exchange_rates as ex

GOOD = {"INR": 1.0, "USD": 0.0105, "EUR": 0.0091, "GBP": 0.0078}


@pytest.fixture(autouse=True)
def _clear_cache():
    ex.reset_cache()
    yield
    ex.reset_cache()


def test_rates_endpoint_returns_all_supported_currencies(client, monkeypatch):
    monkeypatch.setattr(ex, "_fetch", lambda: dict(GOOD))
    r = client.get("/orders/rates")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["base"] == "INR"
    assert body["stale"] is False
    assert set(body["rates"]) == set(ex.SUPPORTED)
    assert body["rates"]["INR"] == 1.0


def test_rates_endpoint_is_public(client, monkeypatch):
    """No Authorization header — the shop's product list is public too."""
    monkeypatch.setattr(ex, "_fetch", lambda: dict(GOOD))
    assert client.get("/orders/rates").status_code == 200


def test_rates_are_cached_between_calls(client, monkeypatch):
    calls = []

    def _counted():
        calls.append(1)
        return dict(GOOD)

    monkeypatch.setattr(ex, "_fetch", _counted)
    client.get("/orders/rates")
    client.get("/orders/rates")
    client.get("/orders/rates")
    assert len(calls) == 1, "expected one upstream fetch, got %d" % len(calls)


def test_falls_back_when_provider_unreachable_and_cache_empty(client, monkeypatch):
    def _boom():
        raise OSError("network down")

    monkeypatch.setattr(ex, "_fetch", _boom)
    r = client.get("/orders/rates")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stale"] is True, "fallback rates must be flagged stale"
    assert set(body["rates"]) == set(ex.SUPPORTED)
    assert all(v > 0 for v in body["rates"].values())


def test_serves_last_good_rates_when_refresh_fails(client, monkeypatch):
    monkeypatch.setattr(ex, "_fetch", lambda: dict(GOOD))
    first = client.get("/orders/rates").json()
    assert first["stale"] is False

    # Expire the cache, then make the refresh fail.
    monkeypatch.setattr(ex, "CACHE_TTL_SECONDS", -1)

    def _boom():
        raise OSError("network down")

    monkeypatch.setattr(ex, "_fetch", _boom)
    second = client.get("/orders/rates").json()
    assert second["stale"] is True
    assert second["rates"] == first["rates"], "should reuse the last good rates"


@pytest.mark.parametrize(
    "bad",
    [
        {"INR": 1.0, "USD": 0.0105, "EUR": 0.0091},           # GBP missing
        {"INR": 1.0, "USD": 0.0, "EUR": 0.0091, "GBP": 0.0078},   # zero rate
        {"INR": 1.0, "USD": -1.0, "EUR": 0.0091, "GBP": 0.0078},  # negative
        {"INR": 1.0, "USD": "x", "EUR": 0.0091, "GBP": 0.0078},   # non-numeric
    ],
)
def test_malformed_provider_payload_is_rejected(bad):
    """A zero or missing rate would render every price as 0.00 — the parser must
    reject the whole payload rather than let one bad value through."""
    import json as _json

    class _Resp:
        def read(self):
            return _json.dumps({"result": "success", "rates": bad}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request

    orig = urllib.request.urlopen
    urllib.request.urlopen = lambda *a, **k: _Resp()
    try:
        with pytest.raises(Exception):
            ex._fetch()
    finally:
        urllib.request.urlopen = orig


def test_rates_route_not_shadowed_by_order_id_route(client, monkeypatch):
    """`/orders/rates` is declared before `/orders/{order_id}`; if that ordering
    regresses, FastAPI would try to parse 'rates' as an int and 422."""
    monkeypatch.setattr(ex, "_fetch", lambda: dict(GOOD))
    r = client.get("/orders/rates")
    assert r.status_code == 200, (
        "GET /orders/rates returned %s — likely captured by /orders/{order_id}" % r.status_code
    )
