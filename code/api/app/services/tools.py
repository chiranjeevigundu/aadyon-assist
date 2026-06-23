"""Agent tools — the only ways an agent can touch the world.

Read tools run automatically. Anything with a side effect does NOT execute:
`propose_action` records a proposal that a human approves. `delegate` only
creates internal sub-tasks in the queue (bookkeeping, not a real-world action).
"""
import json

from app.db.session import query
from app.services.digital_me import digital_me

# OpenAI-style tool schemas, keyed by name.
_SCHEMAS = {
    "get_snapshot": {
        "type": "function",
        "function": {
            "name": "get_snapshot",
            "description": "Get the full Digital Me snapshot: profile, life-since-birth, "
                           "projected income, and the financial/visa/career/goal dimensions "
                           "(including debts, deadlines, applications, goals). Call this first.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "delegate": {
        "type": "function",
        "function": {
            "name": "delegate",
            "description": "Delegate a concrete sub-task to a team. Creates a queued task "
                           "assigned to that team's lead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "team": {"type": "string", "enum": ["Finance", "Immigration", "Career", "Growth"]},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["team", "title"],
            },
        },
    },
    "propose_action": {
        "type": "function",
        "function": {
            "name": "propose_action",
            "description": "Propose a real-world action that needs the human's approval before "
                           "anything happens (e.g. make a payment, send an email, file a form). "
                           "This does NOT execute — it queues a proposal for review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["title", "detail"],
            },
        },
    },
}

# Which tools each org level may use.
_BY_TYPE = {
    "ceo": ["get_snapshot", "delegate"],
    "team_lead": ["get_snapshot", "propose_action"],
    "employee": ["get_snapshot", "propose_action"],
}


def schemas_for(agent_type: str) -> list:
    return [_SCHEMAS[n] for n in _BY_TYPE.get(agent_type, ["get_snapshot"])]


def dispatch(name: str, args: dict, ctx: dict) -> dict:
    """Execute a tool. ctx carries the current task_id, agent_id, team_id."""
    if name == "get_snapshot":
        return digital_me()
    if name == "delegate":
        return _delegate(args, ctx)
    if name == "propose_action":
        return _propose(args, ctx)
    return {"error": f"unknown tool {name}"}


def _delegate(args: dict, ctx: dict) -> dict:
    team = args.get("team")
    rows = query("SELECT id FROM teams WHERE name = %s", (team,))
    if not rows:
        return {"error": f"no team named {team}"}
    team_id = rows[0]["id"]
    lead = query(
        "SELECT id FROM agents WHERE team_id = %s AND agent_type = 'team_lead' "
        "AND active ORDER BY created_at LIMIT 1",
        (team_id,),
    )
    lead_id = lead[0]["id"] if lead else None
    created = query(
        "INSERT INTO tasks (title, description, kind, team_id, agent_id, parent_id, "
        "status, created_by) VALUES (%s,%s,'task',%s,%s,%s,'queued','ceo') RETURNING id",
        (args.get("title"), args.get("description"), team_id, lead_id, ctx.get("task_id")),
        commit=True,
    )
    return {"delegated_to": team, "task_id": str(created[0]["id"])}


def _propose(args: dict, ctx: dict) -> dict:
    detail = args.get("detail", "")
    if args.get("category"):
        detail = f"[{args['category']}] {detail}"
    created = query(
        "INSERT INTO tasks (title, description, kind, team_id, parent_id, status, "
        "requires_approval, created_by) VALUES (%s,%s,'proposal',%s,%s,"
        "'awaiting_approval', true, 'agent') RETURNING id",
        (args.get("title"), detail, ctx.get("team_id"), ctx.get("task_id")),
        commit=True,
    )
    return {"proposal_id": str(created[0]["id"]), "status": "awaiting_approval"}
