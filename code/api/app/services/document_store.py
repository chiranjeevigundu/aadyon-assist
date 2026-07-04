"""Persistence for document/email extractions.

Applies extracted items to deadlines / bills / subscriptions, with dedup so a
recurring statement (or repeated email) updates the existing record instead of
piling up duplicates. Shared by manual approval and the auto-apply path.
"""
import json

from app.db.session import current_user_id, query
from app.services.email_extract import coerce_due


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def apply_item(kind: str, payload: dict, source: str, uid: str | None = None,
               seen_date=None) -> dict:
    """Create or update a tracked record from one extracted item, deduped by name.

    Returns {"applied_as", "action": created|updated|exists, "id"} on success or
    {"error": ...} when required fields are missing. `source` is a short provenance
    label (e.g. a filename or "email:<subject>") stored in notes on first create.
    `seen_date` is the statement/email date, recorded as last_seen for recurrence.
    """
    uid = uid or current_user_id()
    title = payload.get("title") or source or "From document"
    due = coerce_due(payload.get("due_date"))
    amount = payload.get("amount")
    note = f"From: {source}" if source else None

    if kind == "deadline":
        if not due:
            return {"error": "deadline needs a due_date"}
        existing = query(
            "SELECT id FROM deadlines WHERE lower(title)=%s AND due_date=%s AND status<>'done'",
            (_norm(title), due),
        )
        if existing:
            return {"applied_as": "deadline", "action": "exists", "id": str(existing[0]["id"])}
        rows = query(
            "INSERT INTO deadlines (user_id, title, category, due_date, status, priority, notes) "
            "VALUES (%s,%s,'general',%s,'open',3,%s) RETURNING id",
            (uid, title, due, note), commit=True,
        )
        return {"applied_as": "deadline", "action": "created", "id": str(rows[0]["id"])}

    if kind in ("bill", "subscription"):
        if amount is None:
            return {"error": f"{kind} needs an amount"}
        table = "bills" if kind == "bill" else "subscriptions"
        existing = query(
            f"SELECT id, amount FROM {table} WHERE lower(name)=%s AND active",
            (_norm(title),),
        )
        if existing:
            # Recurrence: refresh last_seen, and update the amount if it changed.
            query(
                f"UPDATE {table} SET amount=%s, last_seen=COALESCE(%s, last_seen) WHERE id=%s",
                (amount, seen_date, existing[0]["id"]), commit=True,
            )
            return {"applied_as": kind, "action": "updated", "id": str(existing[0]["id"])}
        if kind == "bill":
            rows = query(
                "INSERT INTO bills (user_id, name, amount, frequency, category, notes, last_seen) "
                "VALUES (%s,%s,%s,'monthly','other',%s,%s) RETURNING id",
                (uid, title, amount, note, seen_date), commit=True,
            )
        else:
            rows = query(
                "INSERT INTO subscriptions (user_id, name, amount, billing_cycle, notes, last_seen) "
                "VALUES (%s,%s,%s,'monthly',%s,%s) RETURNING id",
                (uid, title, amount, note, seen_date), commit=True,
            )
        return {"applied_as": kind, "action": "created", "id": str(rows[0]["id"])}

    return {"error": f"cannot apply '{kind}' without required fields; dismiss instead"}


def mark_ended(kind: str, name: str, uid: str | None = None) -> dict:
    """Flip a tracked subscription/bill to inactive (e.g. 'my Spotify ended')."""
    table = "bills" if kind == "bill" else "subscriptions"
    rows = query(
        f"UPDATE {table} SET active=false WHERE lower(name)=%s AND active RETURNING id",
        (_norm(name),), commit=True,
    )
    return {"ok": bool(rows), "action": f"ended {kind}" if rows else "no active match"}


def approve_extraction(ext_id: str) -> dict:
    rows = query(
        "SELECT e.*, d.filename FROM document_extractions e "
        "JOIN documents d ON d.id = e.document_id WHERE e.id=%s",
        (ext_id,),
    )
    if not rows:
        return {"error": "not found"}
    e = rows[0]
    payload = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
    res = apply_item(e["kind"], payload, e["filename"])
    if res.get("error"):
        return res
    query("UPDATE document_extractions SET status='approved' WHERE id=%s", (ext_id,), commit=True)
    return {"status": "approved", "applied_as": res["applied_as"], "action": res["action"]}
