"""Model routing: tier -> (provider, model, temperature), with DB row or fallback."""
from app.services import routing
from conftest import patch_query


def test_resolve_uses_db_row(monkeypatch):
    patch_query(monkeypatch, "app.services.routing",
                [[{"provider": "ollama", "model_id": "llama3.1", "temperature": 0.5}]])
    r = routing.resolve("local")
    assert r == {"provider": "ollama", "model": "llama3.1", "temperature": 0.5}


def test_resolve_falls_back_to_defaults(monkeypatch):
    patch_query(monkeypatch, "app.services.routing", [[]])  # no row
    r = routing.resolve("reasoning")
    assert r["provider"] == "openrouter"
    assert r["model"] == "openrouter/auto"
    assert r["temperature"] == 0.2


def test_resolve_unknown_tier_falls_back_to_reasoning(monkeypatch):
    patch_query(monkeypatch, "app.services.routing", [[]])
    r = routing.resolve("does-not-exist")
    assert r["model"] == "openrouter/auto"


def test_resolve_null_temperature_defaults(monkeypatch):
    patch_query(monkeypatch, "app.services.routing",
                [[{"provider": "openrouter", "model_id": "x", "temperature": None}]])
    assert routing.resolve("reasoning")["temperature"] == 0.2
