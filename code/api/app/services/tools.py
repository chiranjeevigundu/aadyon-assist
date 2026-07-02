"""Agent tools — the ways an agent (org worker or the personal assistant) can act.

Two boundaries, matching the golden rules:
- READ tools (`get_snapshot`) run automatically.
- INTERNAL WRITE tools (`create_/update_/delete_*`, `update_profile`) change the
  user's OWN records directly — authorized, low-stakes, and RLS-scoped to them.
- EXTERNAL side effects (`propose_action`) do NOT execute: they queue a proposal a
  human approves (money, email, filings). `delegate` only creates internal subtasks.

Write-tool schemas are generated from the CRUD column whitelists in models.tables
(one source of truth) so they can never touch a non-writable column.
"""
import json  # noqa: F401 — kept for parity/backwards-compat with callers

from app.db.session import current_user_id, query
from app.models.tables import ENTITIES
from app.services.digital_me import digital_me

_COLS = {e.table: list(e.columns) for e in ENTITIES}

# Tables the personal assistant may create/update/delete directly (the user's own
# life-ops records). Profile is handled separately as a per-user singleton upsert.
_WRITE_TABLES = ["deadlines", "bills", "debts", "subscriptions", "milestones"]

# Minimum fields the model must provide to make a useful new row.
_REQUIRED = {
    "deadlines": ["title", "due_date"],
    "bills": ["name", "amount"],
    "debts": ["name", "balance", "apr"],
    "subscriptions": ["name", "amount"],
    "milestones": ["title"],
}

_NUMERIC_HINTS = ("amount", "balance", "apr", "rate", "pay", "salary", "income",
                  "limit", "payment", "min_payment", "pct", "progress", "hours",
                  "day", "port", "term_months", "installments", "priority", "year")
_BOOL_COLS = {"autopay", "active", "achieved"}


def _param_type(col: str) -> dict:
    if col in _BOOL_COLS:
        return {"type": "boolean"}
    if "date" in col or col.endswith("_on") or col in ("renews_on", "work_auth_until"):
        return {"type": "string", "description": "ISO date, YYYY-MM-DD"}
    if any(h in col for h in _NUMERIC_HINTS):
        return {"type": "number"}
    return {"type": "string"}


def _props(cols: list[str]) -> dict:
    return {c: _param_type(c) for c in cols}


# --------------------------------------------------------------------------- schemas
_SCHEMAS: dict = {
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
    "update_profile": {
        "type": "function",
        "function": {
            "name": "update_profile",
            "description": "Update the user's profile/identity fields (name, location, visa, "
                           "target role/salary, current income, goal, etc.). Only pass fields to change.",
            "parameters": {"type": "object", "properties": _props(_COLS["profile"])},
        },
    },
}


# Maps a (singular) write tool name -> the table it acts on, e.g.
# "create_deadline" -> "deadlines". Filled by _build_write_schemas().
_TOOL_TABLE: dict[str, str] = {}


def _build_write_schemas() -> None:
    """Generate singular create_/update_/delete_ tools for each writable table."""
    verbs = {
        "create": "Create a new {s} record for the user.",
        "update": "Update an existing {s} record by id. Only pass fields to change.",
        "delete": "Delete a {s} record by id.",
    }
    for t in _WRITE_TABLES:
        singular = t[:-1] if t.endswith("s") else t
        cols = _COLS[t]
        # create_<singular>
        _TOOL_TABLE[f"create_{singular}"] = t
        _SCHEMAS[f"create_{singular}"] = {
            "type": "function",
            "function": {
                "name": f"create_{singular}",
                "description": verbs["create"].format(s=singular),
                "parameters": {
                    "type": "object",
                    "properties": _props(cols),
                    "required": _REQUIRED.get(t, []),
                },
            },
        }
        # update_<singular>
        up_props = {"id": {"type": "string", "description": f"id of the {singular} to update"}}
        up_props.update(_props(cols))
        _TOOL_TABLE[f"update_{singular}"] = t
        _SCHEMAS[f"update_{singular}"] = {
            "type": "function",
            "function": {
                "name": f"update_{singular}",
                "description": verbs["update"].format(s=singular),
                "parameters": {"type": "object", "properties": up_props, "required": ["id"]},
            },
        }
        # delete_<singular>
        _TOOL_TABLE[f"delete_{singular}"] = t
        _SCHEMAS[f"delete_{singular}"] = {
            "type": "function",
            "function": {
                "name": f"delete_{singular}",
                "description": verbs["delete"].format(s=singular),
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            },
        }


_build_write_schemas()

# Which tools each caller-type may use.
_WRITE_TOOL_NAMES = ["update_profile"] + list(_TOOL_TABLE.keys())
_BY_TYPE = {
    "ceo": ["get_snapshot", "delegate"],
    "team_lead": ["get_snapshot", "propose_action"],
    "employee": ["get_snapshot", "propose_action"],
    # The personal assistant: read, write the user's own data, and propose externals.
    "assistant": ["get_snapshot"] + _WRITE_TOOL_NAMES + ["propose_action"],
}


def schemas_for(agent_type: str) -> list:
    return [_SCHEMAS[n] for n in _BY_TYPE.get(agent_type, ["get_snapshot"]) if n in _SCHEMAS]


# --------------------------------------------------------------------------- dispatch
def dispatch(name: str, args: dict, ctx: dict) -> dict:
    """Execute a tool. ctx carries task_id/agent_id/team_id (org) or is minimal (assistant)."""
    if name == "get_snapshot":
        return digital_me()
    if name == "delegate":
        return _delegate(args, ctx)
    if name == "propose_action":
        return _propose(args, ctx)
    if name == "update_profile":
        return _update_profile(args)
    table = _TOOL_TABLE.get(name)
    if table:
        if name.startswith("create_"):
            return _create(table, args)
        if name.startswith("update_"):
            return _update(table, args)
        if name.startswith("delete_"):
            return _delete(table, args)
    return {"error": f"unknown tool {name}"}


# --------------------------------------------------------------------------- write handlers
def _create(table: str, args: dict) -> dict:
    cols = _COLS[table]
    data = {k: v for k, v in args.items() if k in cols and v is not None}
    missing = [c for c in _REQUIRED.get(table, []) if c not in data]
    if missing:
        return {"error": f"missing required fields: {missing}"}
    data["user_id"] = current_user_id()
    fields = ", ".join(data.keys())
    ph = ", ".join(["%s"] * len(data))
    rows = query(
        f"INSERT INTO {table} ({fields}) VALUES ({ph}) RETURNING *",
        tuple(data.values()), commit=True,
    )
    return {"ok": True, "action": f"created {table}", "row": rows[0] if rows else None}


def _update(table: str, args: dict) -> dict:
    row_id = args.get("id")
    if not row_id:
        return {"error": "id is required"}
    cols = _COLS[table]
    data = {k: v for k, v in args.items() if k in cols and v is not None}
    if not data:
        return {"error": "no fields to update"}
    sets = ", ".join(f"{k} = %s" for k in data)
    rows = query(
        f"UPDATE {table} SET {sets} WHERE id = %s RETURNING *",
        tuple(data.values()) + (row_id,), commit=True,
    )
    if not rows:
        return {"error": "not found"}
    return {"ok": True, "action": f"updated {table}", "row": rows[0]}


def _delete(table: str, args: dict) -> dict:
    row_id = args.get("id")
    if not row_id:
        return {"error": "id is required"}
    rows = query(f"DELETE FROM {table} WHERE id = %s RETURNING id", (row_id,), commit=True)
    return {"ok": bool(rows), "action": f"deleted {table}" if rows else "not found"}


def _update_profile(args: dict) -> dict:
    cols = _COLS["profile"]
    data = {k: v for k, v in args.items() if k in cols and v is not None}
    if not data:
        return {"error": "no profile fields provided"}
    existing = query("SELECT id FROM profile LIMIT 1")  # RLS-scoped to this user
    if existing:
        sets = ", ".join(f"{k} = %s" for k in data)
        query(f"UPDATE profile SET {sets} WHERE id = %s",
              tuple(data.values()) + (existing[0]["id"],), commit=True)
        return {"ok": True, "action": "updated profile"}
    # No profile yet — create it (full_name is NOT NULL).
    data.setdefault("full_name", "Me")
    data["user_id"] = current_user_id()
    fields = ", ".join(data.keys())
    ph = ", ".join(["%s"] * len(data))
    query(f"INSERT INTO profile ({fields}) VALUES ({ph})", tuple(data.values()), commit=True)
    return {"ok": True, "action": "created profile"}


# --------------------------------------------------------------------------- org handlers
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
        "INSERT INTO tasks (user_id, title, description, kind, team_id, agent_id, parent_id, "
        "status, created_by) VALUES (%s,%s,%s,'task',%s,%s,%s,'queued','ceo') RETURNING id",
        (current_user_id(), args.get("title"), args.get("description"), team_id, lead_id,
         ctx.get("task_id")),
        commit=True,
    )
    return {"delegated_to": team, "task_id": str(created[0]["id"])}


def _propose(args: dict, ctx: dict) -> dict:
    detail = args.get("detail", "")
    if args.get("category"):
        detail = f"[{args['category']}] {detail}"
    created = query(
        "INSERT INTO tasks (user_id, title, description, kind, team_id, parent_id, status, "
        "requires_approval, created_by) VALUES (%s,%s,%s,'proposal',%s,%s,"
        "'awaiting_approval', true, 'agent') RETURNING id",
        (current_user_id(), args.get("title"), detail, ctx.get("team_id"), ctx.get("task_id")),
        commit=True,
    )
    return {"proposal_id": str(created[0]["id"]), "status": "awaiting_approval",
            "note": "Queued for your approval — nothing executed."}
