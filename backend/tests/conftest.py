"""
Pytest fixtures: an isolated SQLite database and a FastAPI TestClient.

We point DATABASE_URL at a throwaway SQLite file *before* importing the app, so
`create_all` + the boot migrations run against SQLite (the MySQL-only MODIFY
steps are dialect-guarded and skip). The per-device advisory lock uses MySQL's
GET_LOCK/RELEASE_LOCK, which don't exist in SQLite — we register no-op SQLite
functions so the start/cancel endpoints work under test.
"""
import os
import pathlib

TEST_DB = "/tmp/sbf_pytest.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret-" + "x" * 40  # passes the strong-key check

# Start from a clean schema every test session.
pathlib.Path(TEST_DB).unlink(missing_ok=True)

import pytest
from sqlalchemy import event
from starlette.testclient import TestClient

from app.database import engine, Base, get_db, SessionLocal


@event.listens_for(engine, "connect")
def _register_sqlite_lock_shims(dbapi_conn, _record):
    # MySQL advisory-lock functions, no-op'd for SQLite tests.
    dbapi_conn.create_function("GET_LOCK", 2, lambda name, timeout: 1)
    dbapi_conn.create_function("RELEASE_LOCK", 1, lambda name: 1)


# Importing the app triggers route registration + create_all + boot migrations.
import app.main  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """The /auth limiters key by client IP and TestClient shares one host, so
    clear their state before every test to keep tests independent."""
    from app.utils.rate_limiter import login_limiter, register_limiter
    login_limiter._log.clear()
    register_limiter._log.clear()
    yield


@pytest.fixture()
def client():
    """A TestClient whose get_db yields a session on the test SQLite engine."""
    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Note: we deliberately do NOT use `with TestClient(app)` — that would run
    # the app's startup events (APScheduler), which conflict across tests and
    # aren't needed here. Plain instantiation skips lifespan events.
    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


_user_seq = 0
_device_seq = 0


@pytest.fixture()
def auth(client):
    """
    Factory that registers a fresh user and returns (headers, user_payload).
    Each call uses a unique email so tests are independent.
    """
    def _make(password="Sup3rSecret!"):
        global _user_seq
        _user_seq += 1
        email = f"user{_user_seq}@test.com"
        r = client.post(
            "/auth/register",
            json={"email": email, "full_name": "Test User", "password": password},
        )
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, {"email": email, "password": password}

    return _make


@pytest.fixture()
def make_device(client):
    """Factory: register a device for the given auth headers, return (device_id, api_key)."""
    def _make(headers):
        global _device_seq
        _device_seq += 1
        mac = f"AA:BB:CC:DD:{(_device_seq >> 8) & 0xFF:02X}:{_device_seq & 0xFF:02X}"
        r = client.post(
            "/devices/",
            headers=headers,
            json={"device_name": "Test Dev", "mac_address": mac, "wifi_ssid": "wifi"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        return body["id"], body["api_key"]

    return _make
