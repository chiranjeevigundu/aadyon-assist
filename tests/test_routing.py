"""Model routing: tier -> (provider, model, temperature) from config defaults."""
from app.services import routing


def test_resolve_reasoning_tier():
    r = routing.resolve("reasoning")
    assert r["provider"] == "openrouter"
    assert r["model"] == "openrouter/auto"
    assert r["temperature"] == 0.2


def test_resolve_local_tier():
    assert routing.resolve("local") == {
        "provider": "ollama", "model": "llama3.1", "temperature": 0.2,
    }


def test_resolve_unknown_tier_falls_back_to_reasoning():
    assert routing.resolve("does-not-exist")["model"] == "openrouter/auto"
