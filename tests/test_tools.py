"""Assistant tools: schemas + dispatch (reads run automatically, propose only queues)."""
from app.services import tools
from conftest import patch_query


def test_assistant_schema_is_financial():
    names = [s["function"]["name"] for s in tools.schemas_for("assistant")]
    assert "get_snapshot" in names
    assert "propose_action" in names
    assert "create_debt" in names and "create_asset" in names
    # removed agency / persona tools are gone
    assert "delegate" not in names
    assert "get_tasks" not in names
    assert "get_calendar" not in names
    # Unknown role gets read-only.
    assert [s["function"]["name"] for s in tools.schemas_for("???")] == ["get_snapshot"]


def test_get_snapshot_returns_net_worth(monkeypatch):
    monkeypatch.setattr(tools, "net_worth_summary", lambda: {"net_worth": 12000.0})
    assert tools.dispatch("get_snapshot", {}, {}) == {"net_worth": 12000.0}


def test_propose_action_queues_for_approval(monkeypatch):
    fake = patch_query(monkeypatch, "app.services.tools", [[{"id": "prop-3"}]])
    out = tools.dispatch(
        "propose_action", {"title": "pay card", "detail": "$50", "category": "bill"}, {}
    )
    assert out["proposal_id"] == "prop-3"
    assert out["status"] == "pending"
    assert "note" in out  # external side effects are queued, never executed
    assert "INSERT INTO proposals" in fake.calls[-1][0]


def test_unknown_tool():
    assert "error" in tools.dispatch("nope", {}, {})
