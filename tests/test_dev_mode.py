"""DEV_MODE gates the developer surfaces.

CI's smoke job runs with DEV_MODE=true (the contract fuzz needs /openapi.json), so
these tests are what actually guarantee the *production* behaviour: with the flag
off, the raw table console and the auto-generated API docs must not be served.
"""
import importlib

import pytest
from fastapi.testclient import TestClient


def _client(monkeypatch, dev_mode: str):
    """Build a fresh app with DEV_MODE set. Settings are lru_cached and the docs
    routes are decided at app construction, so both must be rebuilt per case."""
    monkeypatch.setenv("DEV_MODE", dev_mode)
    from app.core import config

    config.get_settings.cache_clear()
    main = importlib.import_module("app.main")
    return TestClient(main.create_app())


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Never leak a DEV_MODE-flavoured Settings into another test."""
    yield
    from app.core import config

    config.get_settings.cache_clear()


def test_dev_surfaces_hidden_by_default(monkeypatch):
    c = _client(monkeypatch, "false")
    assert c.get("/data").status_code == 404
    assert c.get("/docs").status_code == 404
    assert c.get("/redoc").status_code == 404
    assert c.get("/openapi.json").status_code == 404


def test_dev_surfaces_available_when_enabled(monkeypatch):
    c = _client(monkeypatch, "true")
    assert c.get("/docs").status_code == 200
    assert c.get("/openapi.json").status_code == 200


def test_app_config_reports_the_flag(monkeypatch):
    off = _client(monkeypatch, "false").get("/api/app-config").json()
    assert off["dev_mode"] is False

    on = _client(monkeypatch, "true").get("/api/app-config").json()
    assert on["dev_mode"] is True


def test_app_config_exposes_nothing_sensitive(monkeypatch):
    """It is public (no auth), so it must stay a minimal flag payload."""
    body = _client(monkeypatch, "false").get("/api/app-config").json()
    assert set(body) == {"dev_mode"}


def test_product_routes_unaffected_by_the_flag(monkeypatch):
    c = _client(monkeypatch, "false")
    for path in ("/", "/tracker", "/assistant", "/accounts", "/login"):
        assert c.get(path).status_code == 200, path
