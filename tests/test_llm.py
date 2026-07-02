"""LLM client over LiteLLM: model-string composition, key gate, error mapping, health."""
import pytest

from app.core.config import get_settings
from app.services import llm
from app.services.llm import LLMError


class _Msg:
    def __init__(self, content="hi", tool_calls=None):
        self._d = {"role": "assistant", "content": content, "tool_calls": tool_calls}

    def model_dump(self):
        return dict(self._d)


class _Usage:
    def model_dump(self):
        return {"total_tokens": 7}


class _Completion:
    def __init__(self, **msg_kwargs):
        self.choices = [type("C", (), {"message": _Msg(**msg_kwargs)})()]
        self.usage = _Usage()


def _capture(monkeypatch, **msg_kwargs):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _Completion(**msg_kwargs)

    monkeypatch.setattr(llm.litellm, "completion", fake_completion)
    return captured


def test_openrouter_model_prefix_and_normalized_shape(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    captured = _capture(monkeypatch)
    out = llm.chat("openrouter", "openai/gpt-4o-mini", [{"role": "user", "content": "x"}])
    assert captured["model"] == "openrouter/openai/gpt-4o-mini"
    assert captured["api_key"] == "test-key"
    assert out["provider"] == "openrouter"
    assert out["message"]["content"] == "hi"
    assert out["usage"]["total_tokens"] == 7


def test_openrouter_auto_not_double_prefixed(monkeypatch):
    # model_routes may store the full "openrouter/auto" — must not become openrouter/openrouter/auto
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    captured = _capture(monkeypatch)
    llm.chat("openrouter", "openrouter/auto", [])
    assert captured["model"] == "openrouter/auto"


def test_ollama_uses_chat_route_and_base(monkeypatch):
    captured = _capture(monkeypatch)
    out = llm.chat("ollama", "llama3.1", [{"role": "user", "content": "yo"}])
    assert captured["model"] == "ollama_chat/llama3.1"
    assert captured["api_base"] == get_settings().ollama_base_url
    assert "tools" not in captured          # no tool-calling on the local path
    assert out["model"] == "llama3.1"       # original id echoed back, not the litellm string


def test_openrouter_without_key_raises_before_call(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    def boom(**kwargs):
        raise AssertionError("completion must not be called without a key")

    monkeypatch.setattr(llm.litellm, "completion", boom)
    with pytest.raises(LLMError, match="OPENROUTER_API_KEY"):
        llm.chat("openrouter", "openrouter/auto", [{"role": "user", "content": "x"}])


def test_provider_errors_mapped_to_llmerror(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def boom(**kwargs):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(llm.litellm, "completion", boom)
    with pytest.raises(LLMError, match="rate limited"):
        llm.chat("openrouter", "openrouter/auto", [])


def test_tool_calls_passthrough(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    tc = [{"id": "c1", "type": "function", "function": {"name": "get_snapshot", "arguments": "{}"}}]
    captured = _capture(monkeypatch, content=None, tool_calls=tc)
    tools = [{"type": "function", "function": {"name": "get_snapshot", "parameters": {}}}]
    out = llm.chat("openrouter", "openrouter/auto", [], tools=tools)
    assert captured["tools"] == tools
    assert out["message"]["tool_calls"] == tc


def test_empty_tool_calls_key_removed(monkeypatch):
    # Parity with the old client: assistant messages without calls carry no tool_calls key.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _capture(monkeypatch, content="done", tool_calls=None)
    out = llm.chat("openrouter", "openrouter/auto", [])
    assert "tool_calls" not in out["message"]


class _Resp:
    def __init__(self, ok=True):
        self.ok = ok


def test_health_reports_reachability(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(llm.requests, "get", lambda *a, **k: _Resp(ok=True))
    h = llm.health()
    assert h["openrouter_key_set"] is True
    assert h["ollama_reachable"] is True
