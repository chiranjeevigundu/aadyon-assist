"""Assistant tools — the ways the personal finance assistant can act.

Two boundaries, matching the golden rules:
- READ tools (`get_snapshot`, `get_transactions`, `read_document`, …) run automatically.
- INTERNAL WRITE tools (`create_/update_/delete_*`, `update_profile`) change the
  user's OWN financial records directly — authorized, low-stakes, RLS-scoped to them.
- EXTERNAL side effects (`propose_action`) do NOT execute: they queue a proposal a
  human approves (moving money, sending email, paying a bill).

Write-tool schemas are generated from the CRUD column whitelists in models.tables
(one source of truth) so they can never touch a non-writable column.
"""
import json  # noqa: F401 — kept for parity/backwards-compat with callers

from app.db.session import current_user_id, query
from app.models.tables import ENTITIES
from app.services.networth import net_worth_summary

_COLS = {e.table: list(e.columns) for e in ENTITIES}

# Tables the personal assistant may create/update/delete directly (the user's own
# financial records). Profile is handled separately as a per-user singleton upsert.
_WRITE_TABLES = ["deadlines", "bills", "debts", "subscriptions", "assets"]

# Minimum fields the model must provide to make a useful new row.
_REQUIRED = {
    "deadlines": ["title", "due_date"],
    "bills": ["name", "amount"],
    "debts": ["name", "balance", "apr"],
    "subscriptions": ["name", "amount"],
    "assets": ["name", "value"],
}

_NUMERIC_HINTS = ("amount", "balance", "apr", "rate", "pay", "salary", "income",
                  "limit", "payment", "min_payment", "pct", "progress", "hours",
                  "day", "port", "term_months", "installments", "priority", "year")
_BOOL_COLS = {"autopay", "active", "achieved"}


def _param_type(col: str) -> dict:
    if col in _BOOL_COLS:
        return {"type": "boolean"}
    if "date" in col or col.endswith("_on") or col in ("renews_on",):
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
            "description": "Get the user's financial snapshot: net worth (total assets − total "
                           "liabilities), assets broken down by kind, the individual holdings and "
                           "debts, and the net-worth history. Call this first for real numbers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "get_transactions": {
        "type": "function",
        "function": {
            "name": "get_transactions",
            "description": "Get pending bank transactions waiting in the review queue.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "get_document_extractions": {
        "type": "function",
        "function": {
            "name": "get_document_extractions",
            "description": "Get pending items extracted from uploaded documents waiting in the review queue.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "get_recent_documents": {
        "type": "function",
        "function": {
            "name": "get_recent_documents",
            "description": "List the user's recently uploaded documents. Useful to find the document_id of a newly uploaded file.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "read_document": {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read the raw text content of a document by its document_id.",
            "parameters": {
                "type": "object",
                "properties": {"document_id": {"type": "string"}},
                "required": ["document_id"],
            },
        },
    },
    "remember": {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a durable fact about the user for future sessions (a preference, "
                           "a recurring detail, a decision). Use for things worth recalling later — "
                           "not transient chit-chat. These are surfaced back to you automatically.",
            "parameters": {
                "type": "object",
                "properties": {"content": {"type": "string", "description": "the fact to remember"}},
                "required": ["content"],
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
            "description": "Update the user's profile fields (name, location, current income, "
                           "monthly essential expenses, savings goal, etc.). Only pass fields to change.",
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

# Which tools the assistant may use: read, write the user's own financial data, and
# propose external actions (which only queue for approval, never execute).
_WRITE_TOOL_NAMES = ["update_profile"] + list(_TOOL_TABLE.keys())
_BY_TYPE = {
    "assistant": ["get_snapshot", "get_transactions", "get_document_extractions",
                  "get_recent_documents", "read_document", "remember"]
    + _WRITE_TOOL_NAMES + ["propose_action"],
}


def schemas_for(agent_type: str) -> list:
    return [_SCHEMAS[n] for n in _BY_TYPE.get(agent_type, ["get_snapshot"]) if n in _SCHEMAS]


# --------------------------------------------------------------------------- dispatch
def dispatch(name: str, args: dict, ctx: dict) -> dict:
    """Execute a tool. ctx carries task_id/agent_id/team_id (org) or is minimal (assistant).

    Never raises: a failing tool (bad date string, constraint violation, …) must come
    back as an {"error": ...} tool result the model can react to — an escaped exception
    would 500 the sync chat and tear down the SSE stream mid-response.
    """
    try:
        return _dispatch(name, args, ctx)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _dispatch(name: str, args: dict, ctx: dict) -> dict:
    if name == "get_snapshot":
        return net_worth_summary()
    if name == "get_transactions":
        return _get_transactions(args)
    if name == "get_document_extractions":
        return _get_document_extractions(args)
    if name == "get_recent_documents":
        return _get_recent_documents(args)
    if name == "read_document":
        return _read_document(args)
    if name == "remember":
        return _remember(args)
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
def _clean(args: dict, cols) -> dict:
    """Keep only known columns with real values. The model sends "" for fields it
    has no value for; typed columns (date/numeric) reject empty strings, so treat
    "" the same as absent."""
    return {k: v for k, v in args.items() if k in cols and v is not None and v != ""}


def _create(table: str, args: dict) -> dict:
    data = _clean(args, _COLS[table])
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
    data = _clean(args, _COLS[table])
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
    data = _clean(args, _COLS["profile"])
    if not data:
        return {"error": "no profile fields provided"}
    existing = query("SELECT id FROM profile LIMIT 1")  # RLS-scoped to this user
    if existing:
        sets = ", ".join(f"{k} = %s" for k in data)
        query(f"UPDATE profile SET {sets} WHERE id = %s",
              tuple(data.values()) + (existing[0]["id"],), commit=True)
        action = "updated profile"
    else:
        # No profile yet — create it (full_name is NOT NULL).
        data.setdefault("full_name", "Me")
        data["user_id"] = current_user_id()
        fields = ", ".join(data.keys())
        ph = ", ".join(["%s"] * len(data))
        query(f"INSERT INTO profile ({fields}) VALUES ({ph})", tuple(data.values()), commit=True)
        action = "created profile"
    return {"ok": True, "action": action}


def _remember(args: dict) -> dict:
    """Persist a durable fact for future sessions (surfaced back via the prompt)."""
    content = (args.get("content") or "").strip()
    if not content:
        return {"error": "nothing to remember"}
    query(
        "INSERT INTO memory_chunks (user_id, source, content) VALUES (%s, 'assistant', %s)",
        (current_user_id(), content[:2000]), commit=True,
    )
    return {"ok": True, "action": "remembered"}


def recent_memories(limit: int = 20) -> list[str]:
    """The user's saved facts, newest first — injected into the system prompt so
    the assistant recalls them across sessions."""
    rows = query(
        "SELECT content FROM memory_chunks ORDER BY created_at DESC LIMIT %s", (limit,)
    )
    return [r["content"] for r in rows]


def _get_transactions(args: dict) -> dict:
    rows = query(
        "SELECT transaction_id, date, amount, merchant, category FROM bank_transactions "
        "WHERE status = 'pending' "
        "ORDER BY date DESC LIMIT 50"
    )
    return {"pending_transactions": rows}


def _get_document_extractions(args: dict) -> dict:
    rows = query(
        "SELECT e.id, e.kind, e.summary, e.payload, d.filename FROM document_extractions e "
        "JOIN documents d ON d.id = e.document_id "
        "WHERE e.status = 'pending' "
        "ORDER BY e.created_at DESC LIMIT 50"
    )
    return {"pending_extractions": rows}


def _get_recent_documents(args: dict) -> dict:
    rows = query(
        "SELECT id, filename, mime_type, status, created_at FROM documents "
        "WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
        (current_user_id(),)
    )
    return {"documents": rows}


def _read_document(args: dict) -> dict:
    doc_id = args.get("document_id")
    if not doc_id:
        return {"error": "document_id is required"}
    
    rows = query("SELECT storage_path, mime_type FROM documents WHERE id = %s AND user_id = %s", 
                 (doc_id, current_user_id()))
    if not rows:
        return {"error": "document not found"}
    doc = rows[0]
    
    from app.services import storage
    import io
    
    file_obj = io.BytesIO()
    try:
        storage.download_fileobj(doc["storage_path"], file_obj)
        file_obj.seek(0)
    except Exception as e:
        return {"error": f"failed to download document: {e}"}
        
    mime_type = doc.get("mime_type", "")
    if mime_type == "application/pdf":
        from app.services.document_ingest import extract_text_from_pdf
        return {"text": extract_text_from_pdf(file_obj)}
    
    try:
        return {"text": file_obj.read().decode("utf-8", errors="replace")}
    except Exception as e:
        return {"error": f"could not read document text: {e}"}


# --------------------------------------------------------------------------- proposals
def _propose(args: dict, ctx: dict) -> dict:
    """Queue a real-world external action for the user's approval. Never executes."""
    created = query(
        "INSERT INTO proposals (user_id, title, detail, category, status) "
        "VALUES (%s, %s, %s, %s, 'pending') RETURNING id",
        (current_user_id(), args.get("title"), args.get("detail", ""), args.get("category")),
        commit=True,
    )
    return {"proposal_id": str(created[0]["id"]), "status": "pending",
            "note": "Queued for your approval — nothing executed."}
