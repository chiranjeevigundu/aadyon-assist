"""Agent tools: per-role schemas + dispatch (read auto, delegate/propose queue only)."""
from app.services import tools
from conftest import patch_query


def test_schemas_by_role():
    ceo = [s["function"]["name"] for s in tools.schemas_for("ceo")]
    lead = [s["function"]["name"] for s in tools.schemas_for("team_lead")]
    assert ceo == ["get_snapshot", "delegate"]
    assert lead == ["get_snapshot", "propose_action"]
    # Unknown role gets read-only.
    assert [s["function"]["name"] for s in tools.schemas_for("???")] == ["get_snapshot"]


def test_get_snapshot_calls_digital_me(monkeypatch):
    monkeypatch.setattr(tools, "digital_me", lambda: {"as_of": "2026-06-23"})
    assert tools.dispatch("get_snapshot", {}, {}) == {"as_of": "2026-06-23"}


def test_delegate_creates_subtask(monkeypatch):
    def q(sql, params=(), commit=False):
        if "FROM teams" in sql:
            return [{"id": "team-1"}]
        if "FROM agents" in sql:
            return [{"id": "lead-1"}]
        if sql.strip().startswith("INSERT"):
            return [{"id": "task-9"}]
        return []
    patch_query(monkeypatch, "app.services.tools", q)
    out = tools.dispatch("delegate", {"team": "Finance", "title": "cut interest"},
                         {"task_id": "parent"})
    assert out == {"delegated_to": "Finance", "task_id": "task-9"}


def test_delegate_unknown_team(monkeypatch):
    patch_query(monkeypatch, "app.services.tools", [[]])  # no team
    out = tools.dispatch("delegate", {"team": "Nope", "title": "x"}, {})
    assert "error" in out


def test_propose_action_queues_for_approval(monkeypatch):
    patch_query(monkeypatch, "app.services.tools", [[{"id": "prop-3"}]])
    out = tools.dispatch("propose_action", {"title": "pay card", "detail": "$50"},
                         {"task_id": "t", "team_id": "tm"})
    assert out == {"proposal_id": "prop-3", "status": "awaiting_approval"}


def test_unknown_tool():
    assert "error" in tools.dispatch("nope", {}, {})
