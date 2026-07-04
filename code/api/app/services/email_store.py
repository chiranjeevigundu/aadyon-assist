"""Persistence for email extractions: dedup, queue/auto-apply items, and apply
approved ones to deadlines / bills / subscriptions (shared with documents).
"""
import json

from app.db.session import current_user_id, query
from app.services import document_store
from app.services.email_extract import extract

# High-confidence, unambiguous email items apply straight to the user's records
# (deduped); everything else waits in the review queue. Matches the document path.
_AUTO_APPLY_MIN_CONFIDENCE = 0.8


def already_queued(account_id, message_uid) -> bool:
    """True if this message was already turned into an extraction (any status)."""
    return bool(query(
        "SELECT 1 FROM email_extractions WHERE account_id=%s AND message_uid=%s",
        (account_id, str(message_uid)),
    ))


def insert_extraction(account_id, message_uid, message_date, sender, subject, item, status="pending") -> None:
    """Record one extracted item (pending for review, or auto_applied)."""
    query(
        "INSERT INTO email_extractions (user_id, account_id, message_uid, message_date, sender, "
        "subject, kind, payload, summary, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (current_user_id(), account_id, str(message_uid), message_date, (sender or "")[:300],
         (subject or "")[:300], item.get("kind", "info"), json.dumps(item),
         (item.get("summary") or "")[:500], status),
        commit=True,
    )


def _apply_email_item(item, source, seen_date) -> dict:
    """Route an email item into the shared tracked-record path.

    A cancellation ends the matching active sub/bill; otherwise create/update
    (deduped) like a document item. Returns the apply_item/mark_ended result."""
    kind = item.get("kind")
    if item.get("cancellation") and kind in ("subscription", "bill"):
        name = item.get("title") or ""
        return document_store.mark_ended(kind, name)
    return document_store.apply_item(kind, item, source, seen_date=seen_date)


def process_msg(account_id, msg_id, mdate, sender, subject, body):
    """Dedup + extract + auto-apply/queue one message. Returns (scanned_inc, found_inc)."""
    if already_queued(account_id, msg_id):
        return (0, 0)
    item = extract(sender or "", subject or "", body or "")
    if not item:
        return (1, 0)
    status = "pending"
    if float(item.get("confidence") or 0) >= _AUTO_APPLY_MIN_CONFIDENCE:
        res = _apply_email_item(item, f"email: {sender}", mdate)
        if not res.get("error") and res.get("ok", True):
            status = "auto_applied"
    insert_extraction(account_id, msg_id, mdate, sender, subject, item, status=status)
    return (1, 1)


def approve_extraction(ext_id: str) -> dict:
    rows = query("SELECT * FROM email_extractions WHERE id=%s", (ext_id,))
    if not rows:
        return {"error": "not found"}
    e = rows[0]
    p = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
    # kind is a column on the extraction row, not necessarily inside the payload.
    p.setdefault("kind", e["kind"])
    if not p.get("title"):
        p["title"] = e["subject"] or "From email"
    res = _apply_email_item(p, f"email: {e['sender']}", e.get("message_date"))
    if res.get("error"):
        return res
    query("UPDATE email_extractions SET status='approved' WHERE id=%s", (ext_id,), commit=True)
    return {"status": "approved", "applied_as": res.get("applied_as", e["kind"]),
            "action": res.get("action")}
