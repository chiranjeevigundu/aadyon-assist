"""Assistant write-tools: generated schemas + user-scoped dispatch."""
from app.db.session import set_current_user
from app.services import tools
from conftest import patch_query


def _names(agent_type):
    return [s["function"]["name"] for s in tools.schemas_for(agent_type)]


def test_assistant_has_read_write_and_propose():
    names = _names("assistant")
    assert "get_snapshot" in names
    assert "propose_action" in names          # external side effects still gated
    assert "create_deadline" in names
    assert "update_bill" in names
    assert "delete_subscription" in names
    assert "update_profile" in names


def test_generated_schemas_are_valid_openai_tools():
    schema = next(s for s in tools.schemas_for("assistant")
                  if s["function"]["name"] == "create_deadline")
    fn = schema["function"]
    assert schema["type"] == "function"
    assert fn["parameters"]["type"] == "object"
    # required fields come from the curated map
    assert set(fn["parameters"]["required"]) == {"title", "due_date"}
    assert "title" in fn["parameters"]["properties"]


def test_create_injects_user_id(monkeypatch):
    set_current_user("user-42")
    fake = patch_query(monkeypatch, "app.services.tools",
                       lambda sql, p=(), c=False: [{"id": "d1", "title": "Renew passport"}]
                       if sql.strip().startswith("INSERT") else [])
    out = tools.dispatch("create_deadline",
                         {"title": "Renew passport", "due_date": "2026-08-01", "bogus": "x"}, {})
    assert out["ok"] is True
    insert = next(c for c in fake.calls if c[0].strip().startswith("INSERT"))
    assert "INSERT INTO deadlines" in insert[0]
    assert "user_id" in insert[0]
    assert "bogus" not in insert[0]            # non-whitelisted field dropped
    assert "user-42" in insert[1]              # owner bound from context


def test_create_missing_required(monkeypatch):
    set_current_user("u1")
    patch_query(monkeypatch, "app.services.tools", lambda *a, **k: [])
    out = tools.dispatch("create_deadline", {"title": "no date"}, {})
    assert "error" in out and "due_date" in out["error"]


def test_update_requires_id(monkeypatch):
    set_current_user("u1")
    patch_query(monkeypatch, "app.services.tools", lambda *a, **k: [])
    assert "error" in tools.dispatch("update_bill", {"amount": 20}, {})


def test_update_builds_scoped_update(monkeypatch):
    set_current_user("u1")
    fake = patch_query(monkeypatch, "app.services.tools",
                       lambda sql, p=(), c=False: [{"id": "b1", "amount": 20}]
                       if sql.strip().startswith("UPDATE") else [])
    out = tools.dispatch("update_bill", {"id": "b1", "amount": 20}, {})
    assert out["ok"] is True
    upd = next(c for c in fake.calls if c[0].strip().startswith("UPDATE"))
    assert "UPDATE bills SET" in upd[0] and "WHERE id = %s" in upd[0]


def test_delete_dispatch(monkeypatch):
    set_current_user("u1")
    patch_query(monkeypatch, "app.services.tools",
                lambda sql, p=(), c=False: [{"id": "s1"}] if "DELETE" in sql else [])
    assert tools.dispatch("delete_subscription", {"id": "s1"}, {})["ok"] is True


def test_update_profile_upserts(monkeypatch):
    set_current_user("u1")

    def q(sql, p=(), c=False):
        if sql.strip().startswith("SELECT id FROM profile"):
            return [{"id": "p1"}]          # profile exists -> UPDATE path
        return []
    patch_query(monkeypatch, "app.services.tools", q)
    out = tools.dispatch("update_profile", {"target_salary": 150000}, {})
    assert out["ok"] is True and "profile" in out["action"]


def test_non_writable_table_rejected():
    set_current_user("u1")
    assert "error" in tools.dispatch("delete_agents", {"id": "x"}, {})


def test_update_profile_drops_empty_strings(monkeypatch):
    # The model sends "" for fields it has no value for; "" into a date/numeric
    # column is a DB error (the bug behind the visa-update 503) — must be skipped.
    set_current_user("u1")

    def q(sql, p=(), c=False):
        if sql.strip().startswith("SELECT id FROM profile"):
            return [{"id": "p1"}]
        return []
    fake = patch_query(monkeypatch, "app.services.tools", q)
    out = tools.dispatch(
        "update_profile",
        {"visa_type": "F-1", "visa_status": "student", "birthdate": "", "preferred_name": ""},
        {},
    )
    assert out["ok"] is True
    upd = next(c for c in fake.calls if c[0].strip().startswith("UPDATE profile"))
    assert "visa_type" in upd[0] and "visa_status" in upd[0]
    assert "birthdate" not in upd[0] and "preferred_name" not in upd[0]


def test_update_profile_all_empty_is_a_clean_error(monkeypatch):
    set_current_user("u1")
    patch_query(monkeypatch, "app.services.tools", lambda sql, p=(), c=False: [])
    out = tools.dispatch("update_profile", {"birthdate": "", "headline": ""}, {})
    assert "error" in out


def test_dispatch_returns_tool_exceptions_as_errors(monkeypatch):
    # A handler blowing up (e.g. psycopg2 rejecting a malformed date) must come
    # back as an {"error": ...} tool result, not escape and kill the SSE stream.
    set_current_user("u1")

    def q(sql, p=(), c=False):
        raise ValueError("invalid input syntax for type date")
    patch_query(monkeypatch, "app.services.tools", q)
    out = tools.dispatch("update_profile", {"birthdate": "not-a-date"}, {})
    assert "error" in out and "invalid input" in out["error"]


def test_setting_a_goal_mirrors_it_into_a_milestone(monkeypatch):
    # goal_title/goal_target_date are display labels; the Goal score only reads
    # milestones — a stated goal must create one (at 0%) to show up at all.
    set_current_user("u1")

    def q(sql, p=(), c=False):
        s = sql.strip()
        if s.startswith("SELECT id FROM profile"):
            return [{"id": "p1"}]
        if s.startswith("SELECT id FROM milestones"):
            return []                      # not tracked yet
        return []
    fake = patch_query(monkeypatch, "app.services.tools", q)
    out = tools.dispatch("update_profile",
                         {"goal_title": "become debt free by age 30",
                          "goal_target_date": "2029-12-15"}, {})
    assert out["ok"] is True and "milestone" in out["action"]
    ins = next(c for c in fake.calls if "INSERT INTO milestones" in c[0])
    assert ins[1][1] == "become debt free by age 30" and ins[1][2] == "2029-12-15"


def test_goal_milestone_not_duplicated(monkeypatch):
    set_current_user("u1")

    def q(sql, p=(), c=False):
        s = sql.strip()
        if s.startswith("SELECT id FROM profile"):
            return [{"id": "p1"}]
        if s.startswith("SELECT id FROM milestones"):
            return [{"id": "m1"}]          # goal already tracked
        return []
    fake = patch_query(monkeypatch, "app.services.tools", q)
    out = tools.dispatch("update_profile",
                         {"goal_title": "become debt free by age 30",
                          "goal_target_date": "2030-01-01"}, {})
    assert out["ok"] is True and "milestone" not in out["action"]
    assert not any("INSERT INTO milestones" in c[0] for c in fake.calls)
    upd = next(c for c in fake.calls if "UPDATE milestones SET milestone_date" in c[0])
    assert upd[1] == ("2030-01-01", "m1")  # target date refresh still lands


def test_create_milestone_dedupes_open_title(monkeypatch):
    # A goal auto-mirrored by update_profile shouldn't be duplicated when the model
    # also calls create_milestone for it — dedupe open milestones by title.
    set_current_user("u1")

    def q(sql, p=(), c=False):
        if "SELECT id FROM milestones" in sql:
            return [{"id": "m-existing"}]
        return [{"id": "m-new"}]
    fake = patch_query(monkeypatch, "app.services.tools", q)
    out = tools.dispatch("create_milestone",
                         {"title": "Become debt free by age 30", "category": "goal"}, {})
    assert out["ok"] is True and out["row"]["id"] == "m-existing"
    assert not any("INSERT INTO milestones" in c[0] for c in fake.calls)
