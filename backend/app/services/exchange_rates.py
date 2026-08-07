"""
Live INR→foreign exchange rates for the shop's currency selector.

Rates are fetched from a free, key-less endpoint and cached in memory for
CACHE_TTL_SECONDS, so a busy shop page makes at most one outbound call per TTL
window per worker. Uses stdlib urllib rather than a new dependency, matching
utils/email.py — requirements.txt deliberately carries no HTTP client.

These rates are for DISPLAY ONLY. Orders are priced, stored and charged in INR
(see routers/orders.py — Product.price and Order.total_price have no currency
dimension). The API response carries `stale` and `fetched_at` so the UI can be
honest about how current the numbers are.
"""
import json
import logging
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

BASE = "INR"
# The currencies the client asked to support, plus the INR base.
SUPPORTED = ("INR", "USD", "EUR", "GBP")

# open.er-api.com: free, no API key, no attribution requirement, updates daily.
RATES_ENDPOINT = f"https://open.er-api.com/v6/latest/{BASE}"

CACHE_TTL_SECONDS = 6 * 60 * 60  # 6h — daily-updated source, so this is ample
FETCH_TIMEOUT_SECONDS = 8

# Last-resort rates, used only when the provider is unreachable AND nothing has
# been cached yet (e.g. the very first request after a deploy while the network
# is down). Deliberately approximate — any response built from these is flagged
# `stale: true` so the UI can say so rather than presenting them as live.
# Captured 2026-08.
_FALLBACK: dict[str, float] = {
    "INR": 1.0,
    "USD": 0.0114,
    "EUR": 0.0098,
    "GBP": 0.0085,
}

# (rates, fetched_at_epoch) — module-level, so per-process (per gunicorn worker).
_cache: tuple[dict[str, float], float] | None = None


def _fetch() -> dict[str, float]:
    """Fetch fresh rates. Raises on any network/parse/shape problem."""
    req = urllib.request.Request(
        RATES_ENDPOINT,
        headers={"User-Agent": "unova-backend/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
        payload = json.loads(resp.read().decode())

    if payload.get("result") != "success":
        raise ValueError(f"provider returned result={payload.get('result')!r}")

    rates = payload.get("rates") or {}
    out: dict[str, float] = {}
    for code in SUPPORTED:
        value = rates.get(code)
        # Reject anything non-positive or non-numeric rather than letting a bad
        # value through — a zero rate would render every price as 0.00.
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"missing or invalid rate for {code}: {value!r}")
        out[code] = float(value)
    return out


def get_rates() -> dict:
    """
    Return {"base", "rates", "fetched_at", "stale"} for the supported currencies.

    Never raises: on a failed refresh it serves the last good cached rates (or
    the bundled fallback) and marks the response stale, because a shop page that
    renders slightly-old prices beats one that renders an error.
    """
    global _cache
    now = time.time()

    if _cache is not None:
        rates, fetched_at = _cache
        if now - fetched_at < CACHE_TTL_SECONDS:
            return {
                "base": BASE,
                "rates": rates,
                "fetched_at": fetched_at,
                "stale": False,
            }

    try:
        rates = _fetch()
        _cache = (rates, now)
        return {"base": BASE, "rates": rates, "fetched_at": now, "stale": False}
    except Exception:
        logger.exception("Exchange-rate refresh failed; serving stale/fallback rates")
        if _cache is not None:
            rates, fetched_at = _cache
            return {
                "base": BASE,
                "rates": rates,
                "fetched_at": fetched_at,
                "stale": True,
            }
        return {"base": BASE, "rates": dict(_FALLBACK), "fetched_at": None, "stale": True}


def reset_cache() -> None:
    """Clear the in-memory cache. For tests."""
    global _cache
    _cache = None
