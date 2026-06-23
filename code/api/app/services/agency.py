"""The agency: org tree + the task-running engine.

run_task() drives one agent through a bounded tool-calling loop against the
routed model, logging every step to agent_runs. The CEO delegates to teams;
team leads/employees analyze and (for real-world actions) propose. Read tools
run automatically; nothing with side effects executes without human approval.
"""
import json
from datetime import date

from app.core.config import get_settings
from app.db.session import query
from app.services import routing, tools
from app.services.llm import chat, LLMError, health

RUNNABLE = ("queued", "running")
_CONTENT_CAP = 6000


# --------------------------------------------------------------------------- org
def org_tree() -> dict:
    agents = query("SELECT * FROM agents WHERE active ORDER BY agent_type, name")
    teams = query("SELECT * FROM teams ORDER BY name")
    ceo = next((a for a in agents if a["agent_type"] == "ceo"), None)
    by_team = {}
    for a in agents:
        by_team.setdefault(a.get("team_id"), []).append(a)
    team_nodes = []
    for t in teams:
        members = by_team.get(t["id"], [])
        lead = next((m for m in members if m["agent_type"] == "team_lead"), None)
        employees = [m for m in members if m["agent_type"] == "employee"]
        team_nodes.append({"team": t, "lead": lead, "employees": employees})
    return {"ceo": ceo, "teams": team_nodes}


def _agent(agent_id):
    rows = query("SELECT * FROM agents WHERE id = %s", (agent_id,))
    return rows[0] if rows else None


def _ceo():
    rows = query("SELECT * FROM agents WHERE agent_type = 'ceo' AND active LIMIT 1")
    return rows[0] if rows else None


# --------------------------------------------------------------------------- entry points
def ask_ceo(goal: str, title: str | None = None) -> dict:
    """Create a top-level goal task assigned to the CEO and queue it."""
    ceo = _ceo()
    rows = query(
        "INSERT INTO tasks (title, description, kind, agent_id, status, created_by) "
        "VALUES (%s,%s,'goal',%s,'queued','user') RETURNING *",
        (title or goal[:120], goal, ceo["id"] if ceo else None),
        commit=True,
    )
    return rows[0]


def next_queued():
    rows = query(
        "SELECT id FROM tasks WHERE status = 'queued' "
        "ORDER BY priority ASC, created_at ASC LIMIT 1"
    )
    return rows[0]["id"] if rows else None


# --------------------------------------------------------------------------- approvals
def set_status(task_id, status: str, result: str | None = None):
    query(
        "UPDATE tasks SET status = %s, result = COALESCE(%s, result) WHERE id = %s",
        (status, result, task_id), commit=True,
    )


# --------------------------------------------------------------------------- the engine
def _log(task_id, agent_id, step, provider, model, role, content, tool_name=None, tokens=0):
    query(
        "INSERT INTO agent_runs (task_id, agent_id, step, provider, model, role, "
        "tool_name, content, tokens) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (task_id, agent_id, step, provider, model, role, tool_name,
         (content or "")[:_CONTENT_CAP], tokens), commit=True,
    )


def run_task(task_id) -> dict:
    rows = query("SELECT * FROM tasks WHERE id = %s", (task_id,))
    if not rows:
        return {"error": "task not found"}
    task = rows[0]
    if task["status"] not in RUNNABLE:
        return {"skipped": task["status"]}

    agent = _agent(task["agent_id"]) or _ceo()
    if not agent:
        set_status(task_id, "failed", "no agent available")
        return {"error": "no agent"}

    route = routing.resolve(agent["model_tier"])
    provider, model = route["provider"], route["model"]
    query("UPDATE tasks SET status='running', model_used=%s WHERE id=%s",
          (f"{provider}:{model}", task_id), commit=True)

    ctx = {"task_id": task_id, "agent_id": agent["id"], "team_id": agent.get("team_id")}
    tool_schemas = tools.schemas_for(agent["agent_type"]) if provider == "openrouter" else None

    sys = (agent.get("system_prompt") or "You are a helpful operations agent.") + (
        f"\n\nToday is {date.today()}. You are {agent['name']} ({agent.get('title') or agent['agent_type']}). "
        "Be concrete and brief. Never invent numbers — call get_snapshot for real data. "
        "For anything with a real-world side effect, use propose_action (it requires human approval)."
    )
    messages = [
        {"role": "system", "content": sys},
        {"role": "user", "content": f"TASK: {task['title']}\n\n{task.get('description') or ''}"},
    ]

    try:
        if not tool_schemas:
            # local / no-tools path: single completion
            resp = chat(provider, model, messages, None, route["temperature"])
            content = resp["message"].get("content", "")
            _log(task_id, agent["id"], 0, provider, model, "assistant", content,
                 tokens=resp.get("usage", {}).get("total_tokens", 0))
            set_status(task_id, "done", content)
            return {"status": "done"}

        for step in range(get_settings().agent_max_steps):
            resp = chat(provider, model, messages, tool_schemas, route["temperature"])
            msg = resp["message"]
            tool_calls = msg.get("tool_calls") or []
            _log(task_id, agent["id"], step, provider, model, "assistant",
                 msg.get("content") or ("(calling: " + ", ".join(
                     tc["function"]["name"] for tc in tool_calls) + ")"),
                 tokens=resp.get("usage", {}).get("total_tokens", 0))

            if not tool_calls:
                set_status(task_id, "done", msg.get("content") or "(no output)")
                return {"status": "done"}

            messages.append(msg)
            for tc in tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = tools.dispatch(name, args, ctx)
                payload = json.dumps(result, default=str)
                _log(task_id, agent["id"], step, provider, model, "tool", payload, tool_name=name)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": payload})

        # ran out of steps — keep whatever last content we have
        set_status(task_id, "done", "(reached step limit)")
        return {"status": "done", "note": "step limit"}

    except LLMError as e:
        query("UPDATE tasks SET status='blocked', error=%s WHERE id=%s", (str(e), task_id), commit=True)
        return {"status": "blocked", "error": str(e)}
    except Exception as e:  # noqa: BLE001
        query("UPDATE tasks SET status='failed', error=%s WHERE id=%s", (str(e), task_id), commit=True)
        return {"status": "failed", "error": str(e)}


def llm_health() -> dict:
    h = health()
    h["routes"] = query("SELECT tier, provider, model_id, active FROM model_routes ORDER BY tier")
    return h
