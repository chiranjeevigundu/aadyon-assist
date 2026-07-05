"""Assistant chat engine: the tool-calling loop (model + tools mocked, no DB)."""
import pytest

from app.db.session import set_current_user
from app.services import assistant, tools
from conftest import patch_query


def _base_query(convo=True):
    def q(sql, p=(), c=False):
        if sql.strip().startswith("SELECT id FROM conversations"):
            return [{"id": "c1"}] if convo else []
        if "FROM messages" in sql:
            return []          # empty history
        return []              # INSERT/UPDATE
    return q


def test_missing_conversation_raises(monkeypatch):
    set_current_user("u1")
    patch_query(monkeypatch, "app.services.assistant", _base_query(convo=False))
    with pytest.raises(assistant.ConversationNotFound):
        assistant.run("nope", "hi")


def test_loop_runs_tool_then_final(monkeypatch):
    set_current_user("u1")
    patch_query(monkeypatch, "app.services.assistant", _base_query())
    patch_query(monkeypatch, "app.services.tools", lambda sql, p=(), c=False: [])  # memory injection
    patch_query(monkeypatch, "app.services.usage", lambda sql, p=(), c=False: [])  # budget check
    monkeypatch.setattr(assistant.routing, "resolve",
                        lambda tier: {"provider": "openrouter", "model": "m", "temperature": 0.2})

    turns = iter([
        {"message": {"role": "assistant", "content": None,
                     "tool_calls": [{"id": "tc1", "type": "function",
                                     "function": {"name": "create_deadline",
                                                  "arguments": '{"title":"X","due_date":"2026-08-01"}'}}]},
         "usage": {}},
        {"message": {"role": "assistant", "content": "Added your deadline."}, "usage": {}},
    ])
    monkeypatch.setattr(assistant, "chat", lambda *a, **k: next(turns))
    monkeypatch.setattr(tools, "dispatch",
                        lambda name, args, ctx: {"ok": True, "action": "created deadlines"})

    out = assistant.run("c1", "add a deadline")
    assert out["reply"] == "Added your deadline."
    assert "created deadlines" in out["actions"]


def test_proposal_is_surfaced(monkeypatch):
    set_current_user("u1")
    patch_query(monkeypatch, "app.services.assistant", _base_query())
    patch_query(monkeypatch, "app.services.tools", lambda sql, p=(), c=False: [])  # memory injection
    patch_query(monkeypatch, "app.services.usage", lambda sql, p=(), c=False: [])  # budget check
    monkeypatch.setattr(assistant.routing, "resolve",
                        lambda tier: {"provider": "openrouter", "model": "m", "temperature": 0.2})
    turns = iter([
        {"message": {"role": "assistant", "content": None,
                     "tool_calls": [{"id": "tc1", "type": "function",
                                     "function": {"name": "propose_action",
                                                  "arguments": '{"title":"Pay card","detail":"$50"}'}}]},
         "usage": {}},
        {"message": {"role": "assistant", "content": "Queued a proposal."}, "usage": {}},
    ])
    monkeypatch.setattr(assistant, "chat", lambda *a, **k: next(turns))
    monkeypatch.setattr(tools, "dispatch",
                        lambda name, args, ctx: {"proposal_id": "p9", "status": "awaiting_approval"})
    out = assistant.run("c1", "pay my card")
    assert out["proposals"] == [{"id": "p9", "title": "Pay card"}]


def test_no_tool_provider_single_completion(monkeypatch):
    set_current_user("u1")
    patch_query(monkeypatch, "app.services.assistant", _base_query())
    patch_query(monkeypatch, "app.services.tools", lambda sql, p=(), c=False: [])  # memory injection
    patch_query(monkeypatch, "app.services.usage", lambda sql, p=(), c=False: [])  # budget check
    monkeypatch.setattr(assistant.routing, "resolve",
                        lambda tier: {"provider": "ollama", "model": "llama3.1", "temperature": 0.2})
    monkeypatch.setattr(assistant, "chat",
                        lambda *a, **k: {"message": {"content": "hello there"}, "usage": {}})
    out = assistant.run("c1", "hi")
    assert out["reply"] == "hello there"
    assert out["actions"] == [] and out["proposals"] == []
