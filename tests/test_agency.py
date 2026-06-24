"""Agent engine: org tree, ask_ceo, and the run_task loop (model mocked)."""
from app.services import agency
from app.services.llm import LLMError
from conftest import patch_query

AGENT = {"id": "ag1", "agent_type": "team_lead", "model_tier": "reasoning",
         "name": "Head of Finance", "title": "Lead", "team_id": "t1",
         "system_prompt": "You analyze finances."}
TASK = {"id": "task1", "status": "running", "agent_id": "ag1",
        "title": "Cut interest", "description": "do it"}


def test_org_tree_shape(monkeypatch):
    def q(sql, p=(), c=False):
        if "FROM agents" in sql:
            return [{"id": "ceo", "agent_type": "ceo", "team_id": None, "name": "CEO"},
                    {"id": "l1", "agent_type": "team_lead", "team_id": "t1", "name": "Lead"},
                    {"id": "e1", "agent_type": "employee", "team_id": "t1", "name": "Emp"}]
        if "FROM teams" in sql:
            return [{"id": "t1", "name": "Finance"}]
        return []
    patch_query(monkeypatch, "app.services.agency", q)
    tree = agency.org_tree()
    assert tree["ceo"]["agent_type"] == "ceo"
    assert tree["teams"][0]["team"]["name"] == "Finance"
    assert tree["teams"][0]["lead"]["id"] == "l1"
    assert tree["teams"][0]["employees"][0]["id"] == "e1"


def test_ask_ceo_creates_goal_task(monkeypatch):
    def q(sql, p=(), c=False):
        if "agent_type = 'ceo'" in sql:
            return [{"id": "ceo"}]
        if sql.strip().startswith("INSERT INTO tasks"):
            return [{"id": "t1", "title": "goal", "status": "queued"}]
        return []
    patch_query(monkeypatch, "app.services.agency", q)
    out = agency.ask_ceo("Fix the debt", title="Debt")
    assert out["id"] == "t1" and out["status"] == "queued"


def test_run_task_blocked_when_no_key(monkeypatch):
    patch_query(monkeypatch, "app.services.agency",
                lambda sql, p=(), c=False: [TASK] if "FROM tasks" in sql
                else [AGENT] if "FROM agents" in sql else [])
    monkeypatch.setattr(agency.routing, "resolve",
                        lambda tier: {"provider": "openrouter", "model": "m", "temperature": 0.2})

    def boom(*a, **k):
        raise LLMError("OPENROUTER_API_KEY is not set")

    monkeypatch.setattr(agency, "chat", boom)
    out = agency.run_task("task1")
    assert out["status"] == "blocked"


def test_run_task_local_single_completion(monkeypatch):
    patch_query(monkeypatch, "app.services.agency",
                lambda sql, p=(), c=False: [dict(TASK, agent_id="ag2")] if "FROM tasks" in sql
                else [dict(AGENT, id="ag2", model_tier="local")] if "FROM agents" in sql else [])
    monkeypatch.setattr(agency.routing, "resolve",
                        lambda tier: {"provider": "ollama", "model": "llama3.1", "temperature": 0.2})
    monkeypatch.setattr(agency, "chat",
                        lambda *a, **k: {"message": {"content": "analysis done"}, "usage": {}})
    out = agency.run_task("task1")
    assert out["status"] == "done"


def test_run_task_skips_non_runnable(monkeypatch):
    patch_query(monkeypatch, "app.services.agency",
                lambda sql, p=(), c=False: [dict(TASK, status="done")] if "FROM tasks" in sql else [])
    assert agency.run_task("task1") == {"skipped": "done"}
