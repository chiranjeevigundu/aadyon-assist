"""Model routing: tier -> (provider, model, temperature) from config defaults.

Routing moved to `llmkit.routing` behind an adapter in `services/routing.py`; these
tests cover the contract this application depends on rather than the implementation.
"""
from app.services import routing


def test_resolve_reasoning_tier():
    r = routing.resolve("reasoning")
    assert r["provider"] == "openrouter"
    assert r["model"] == "openrouter/auto"
    assert r["temperature"] == 0.2


def test_resolve_local_tier():
    # Asserts on the keys callers actually use, not on exact dict equality. The
    # extraction added a `tier` key (see below), and an equality assertion here would
    # fail on any additive change — which is the wrong signal, since every caller
    # unpacks by key and none is affected.
    r = routing.resolve("local")
    assert r["provider"] == "ollama"
    assert r["model"] == "llama3.1"
    assert r["temperature"] == 0.2


def test_resolve_unknown_tier_falls_back_to_reasoning():
    assert routing.resolve("does-not-exist")["model"] == "openrouter/auto"


def test_the_returned_tier_is_the_one_actually_used():
    # New in the extraction, and the reason it is worth having: an unknown tier falls
    # back to reasoning, and without this the call would be reported under the tier
    # that was requested rather than the one that ran. Cost-per-tier reporting would
    # quietly attribute reasoning-priced calls to whatever typo produced them.
    assert routing.resolve("cheap")["tier"] == "cheap"
    assert routing.resolve("does-not-exist")["tier"] == "reasoning"


def test_vision_is_a_real_tier():
    # Its absence is why document_ingest hardcoded a provider and model inline,
    # bypassing routing entirely.
    r = routing.resolve("vision")
    assert r["tier"] == "vision"
    assert r["provider"] and r["model"]
