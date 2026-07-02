"""Persistence for email extractions: dedup, queue pending items, and apply
approved ones to deadlines / bills / subscriptions.
"""
import json

from app.db.session import current_user_id, query
from app.services.email_extract import coerce_due, extract


def already_queued(account_id, message_uid) -> bool:
    """True if this message was already turned into an extraction (any status)."""
    return bool(query(
        "SELECT 1 FROM email_extractions WHERE account_id=%s AND message_uid=%s",
        (account_id, str(message_uid)),
    ))


def insert_extraction(account_id, message_uid, message_date, sender, subject, item) -> None:
    """Queue one extracted item for human review (status=pending)."""
    query(
        "INSERT INTO email_extractions (user_id, account_id, message_uid, message_date, sender, "
        "subject, kind, payload, summary, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')",
        (current_user_id(), account_id, str(message_uid), message_date, (sender or "")[:300],
         (subject or "")[:300], item.get("kind", "info"), json.dumps(item),
         (item.get("summary") or "")[:500]),
        commit=True,
    )


def process_msg(account_id, msg_id, mdate, sender, subject, body):
    """Dedup + extract + queue one message. Returns (scanned_inc, found_inc)."""
    if already_queued(account_id, msg_id):
        return (0, 0)
    item = extract(sender or "", subject or "", body or "")
    if not item:
        return (1, 0)
    insert_extraction(account_id, msg_id, mdate, sender, subject, item)
    return (1, 1)


def approve_extraction(ext_id: str) -> dict:
    rows = query("SELECT * FROM email_extractions WHERE id=%s", (ext_id,))
    if not rows:
        return {"error": "not found"}
    e = rows[0]
    p = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
    kind = e["kind"]
    title = p.get("title") or e["subject"] or "From email"
    # Guard against the model's stringly-typed "null" dates on older rows.
    due = coerce_due(p.get("due_date"))
    p["due_date"] = due
    uid = current_user_id()
    if kind == "deadline" and due:
        query("INSERT INTO deadlines (user_id, title, category, due_date, status, priority, notes) "
              "VALUES (%s,%s,'general',%s,'open',3,%s)",
              (uid, title, due, f"From email: {e['sender']}"), commit=True)
    elif kind == "bill" and p.get("amount") is not None:
        query("INSERT INTO bills (user_id, name, amount, frequency, category, notes) "
              "VALUES (%s,%s,%s,'monthly','other',%s)",
              (uid, title, p["amount"], f"From email: {e['sender']}"), commit=True)
    elif kind == "subscription" and p.get("amount") is not None:
        query("INSERT INTO subscriptions (user_id, name, amount, billing_cycle, notes) "
              "VALUES (%s,%s,%s,'monthly',%s)",
              (uid, title, p["amount"], f"From email: {e['sender']}"), commit=True)
    else:
        return {"error": f"cannot apply '{kind}' without required fields; dismiss instead"}
    query("UPDATE email_extractions SET status='approved' WHERE id=%s", (ext_id,), commit=True)
    return {"status": "approved", "applied_as": kind}
