"""The search_documents tool — the assistant's link to the hybrid-rag service.

This is the only tool that leaves the process, so the tests concentrate on what that
adds: the tool must not be advertised when no service is configured, and every network
failure must arrive as a tool result rather than an exception that ends the turn.
"""
import pytest
import requests

from app.services import tools


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.fixture
def configured(monkeypatch):
    """Point the tool at a fake service and clear the settings cache."""
    from app.core.config import get_settings

    monkeypatch.setenv("RAG_SERVICE_URL", "http://rag:8080")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def unconfigured(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.delenv("RAG_SERVICE_URL", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ------------------------------------------------------------------ advertising


def test_the_tool_is_hidden_when_no_service_is_configured(unconfigured):
    # An absent capability and a broken one must not look the same to the model.
    # Advertising a tool that always errors burns a step and teaches distrust.
    names = [s["function"]["name"] for s in tools.schemas_for("assistant")]
    assert "search_documents" not in names
    assert "get_snapshot" in names, "the other tools must still be offered"


def test_the_tool_is_advertised_once_a_service_is_configured(configured):
    names = [s["function"]["name"] for s in tools.schemas_for("assistant")]
    assert "search_documents" in names


def test_it_is_a_read_tool_and_needs_no_approval(configured):
    # Read tools run autonomously; only side-effecting actions become proposals. This
    # asserts search never got grouped with the write surface by accident.
    schema = next(
        s for s in tools.schemas_for("assistant") if s["function"]["name"] == "search_documents"
    )
    assert "query" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["required"] == ["query"]


# ---------------------------------------------------------------------- happy path


def test_a_successful_search_returns_passages_with_citations(configured, monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured.update(url=url, json=json, timeout=timeout)
        return _Response(
            {
                "results": [
                    {
                        "citation": "refunds.md § Refunds > Timeframes",
                        "source": "refunds.md",
                        "section": "Refunds > Timeframes",
                        "text": "International   orders\nget 60 days.",
                    }
                ]
            }
        )

    monkeypatch.setattr(requests, "post", fake_post)
    out = tools.dispatch("search_documents", {"query": "international refund window"}, {})

    assert out["count"] == 1
    assert out["results"][0]["citation"] == "refunds.md § Refunds > Timeframes"
    # Whitespace is normalised so a wrapped passage does not eat context as newlines.
    assert out["results"][0]["text"] == "International orders get 60 days."
    assert captured["url"] == "http://rag:8080/search"
    assert captured["timeout"] > 0, "a request with no timeout can hang the turn forever"


def test_an_empty_result_set_says_so_rather_than_looking_broken(configured, monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Response({"results": []}))
    out = tools.dispatch("search_documents", {"query": "nothing matches"}, {})
    assert out["results"] == [] and "no matching passages" in out["note"]


def test_long_passages_are_trimmed(configured, monkeypatch):
    # Every tool result is persisted to `messages`. Ten full passages per call would
    # dominate the context window and the stored conversation alike.
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: _Response({"results": [{"citation": "c", "text": "x" * 5000}]}),
    )
    out = tools.dispatch("search_documents", {"query": "q"}, {})
    assert len(out["results"][0]["text"]) <= 1200


def test_k_is_clamped_before_reaching_the_service(configured, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, json=None, timeout=None: (captured.update(json), _Response({"results": []}))[1],
    )
    tools.dispatch("search_documents", {"query": "q", "k": 500}, {})
    assert captured["k"] <= 20


# ------------------------------------------------------------------- failure paths


@pytest.mark.parametrize(
    "boom,expected",
    [
        (requests.Timeout("slow"), "timed out"),
        (requests.ConnectionError("refused"), "unavailable"),
        (requests.HTTPError("500"), "unavailable"),
    ],
)
def test_network_failures_come_back_as_tool_results(configured, monkeypatch, boom, expected):
    # A retrieval service being down is an ordinary operational condition. The
    # assistant should report it and continue with the records it can still read,
    # not abandon the turn with an exception.
    def fake_post(*a, **k):
        raise boom

    monkeypatch.setattr(requests, "post", fake_post)
    out = tools.dispatch("search_documents", {"query": "q"}, {})
    assert "error" in out and expected in out["error"]


def test_a_malformed_response_is_reported_not_raised(configured, monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Response(ValueError("not json")))
    out = tools.dispatch("search_documents", {"query": "q"}, {})
    assert "malformed" in out["error"]


def test_an_empty_query_is_rejected_without_a_network_call(configured, monkeypatch):
    def explode(*a, **k):
        raise AssertionError("should not have called the service")

    monkeypatch.setattr(requests, "post", explode)
    assert "error" in tools.dispatch("search_documents", {"query": "   "}, {})


def test_calling_it_unconfigured_returns_an_error_rather_than_crashing(unconfigured):
    # Reachable if a model recalls the tool from earlier context after it was
    # withdrawn — the dispatch path must still be safe.
    out = tools.dispatch("search_documents", {"query": "q"}, {})
    assert "not configured" in out["error"]
