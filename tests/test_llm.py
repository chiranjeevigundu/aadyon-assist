"""LLM client: provider dispatch, Ollama normalization, missing-key error, health."""
import pytest

from app.services import llm
from app.services.llm import LLMError


class _Resp:
    def __init__(self, ok=True, payload=None, status=200, text=""):
        self.ok = ok
        self._payload = payload or {}
        self.status_code = status
        self.text = text
        self.content = b"x"

    def json(self):
        return self._payload


def test_ollama_chat_normalizes(monkeypatch):
    payload = {"message": {"role": "assistant", "content": "hi"},
               "eval_count": 1, "prompt_eval_count": 2}
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(payload=payload))
    out = llm.chat("ollama", "llama3.1", [{"role": "user", "content": "yo"}])
    assert out["provider"] == "ollama"
    assert out["model"] == "llama3.1"
    assert out["message"]["content"] == "hi"
    assert out["usage"]["total_tokens"] == 3


def test_openrouter_without_key_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    with pytest.raises(LLMError):
        llm.chat("openrouter", "openrouter/auto", [{"role": "user", "content": "x"}])


def test_openrouter_http_error_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(llm.requests, "post",
                        lambda *a, **k: _Resp(ok=False, status=500, text="boom"))
    with pytest.raises(LLMError):
        llm.chat("openrouter", "openrouter/auto", [{"role": "user", "content": "x"}])


def test_health_reports_reachability(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(llm.requests, "get", lambda *a, **k: _Resp(ok=True))
    h = llm.health()
    assert h["openrouter_key_set"] is True
    assert h["ollama_reachable"] is True
