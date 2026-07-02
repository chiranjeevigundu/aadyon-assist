"""Persistence for calendar extractions: dedup, queue pending items, and apply
approved ones to deadlines.
"""
import json

from app.db.session import current_user_id, query
from app.services.calendar_extract import extract
from app.services.email_extract import coerce_due


def already_queued(account_id, event_id) -> bool:
    """True if this event was already turned into an extraction (any status)."""
    return bool(query(
        "SELECT 1 FROM calendar_extractions WHERE account_id=%s AND event_id=%s",
        (account_id, str(event_id)),
    ))


def insert_extraction(account_id, event_id, event_date, title, description, item) -> None:
    """Queue one extracted item for human review (status=pending)."""
    query(
        "INSERT INTO calendar_extractions (user_id, account_id, event_id, event_date, summary, "
        "kind, payload, status) VALUES (%s,%s,%s,%s,%s,%s,%s,'pending')",
        (current_user_id(), account_id, str(event_id), event_date, (title or "")[:300],
         item.get("kind", "info"), json.dumps(item)),
        commit=True,
    )


def process_event(account_id, event_id, event_date, title, description):
    """Dedup + extract + queue one event. Returns (scanned_inc, found_inc)."""
    if already_queued(account_id, event_id):
        return (0, 0)
    item = extract(title or "", description or "", event_date)
    if not item:
        return (1, 0)
    insert_extraction(account_id, event_id, event_date, title, description, item)
    return (1, 1)


def approve_extraction(ext_id: str) -> dict:
    rows = query("SELECT * FROM calendar_extractions WHERE id=%s", (ext_id,))
    if not rows:
        return {"error": "not found"}
    e = rows[0]
    p = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
    kind = e["kind"]
    title = p.get("title") or e["summary"] or "From calendar"
    due = coerce_due(p.get("due_date"))
    p["due_date"] = due
    uid = current_user_id()
    
    if kind == "deadline" and due:
        query("INSERT INTO deadlines (user_id, title, category, due_date, status, priority, notes) "
              "VALUES (%s,%s,'general',%s,'open',3,%s)",
              (uid, title, due, "From calendar event"), commit=True)
    else:
        return {"error": f"cannot apply '{kind}' without required fields; dismiss instead"}
    
    query("UPDATE calendar_extractions SET status='approved' WHERE id=%s", (ext_id,), commit=True)
    return {"status": "approved", "applied_as": kind}
