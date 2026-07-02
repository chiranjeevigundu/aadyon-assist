"""Persistence for document extractions.

Applies approved document extractions to deadlines / bills / subscriptions.
"""
import json

from app.db.session import current_user_id, query
from app.services.email_extract import coerce_due

def approve_extraction(ext_id: str) -> dict:
    rows = query(
        "SELECT e.*, d.filename FROM document_extractions e "
        "JOIN documents d ON d.id = e.document_id "
        "WHERE e.id=%s",
        (ext_id,)
    )
    if not rows:
        return {"error": "not found"}
    e = rows[0]
    p = e["payload"] if isinstance(e["payload"], dict) else json.loads(e["payload"])
    kind = e["kind"]
    title = p.get("title") or e["filename"] or "From document"
    due = coerce_due(p.get("due_date"))
    p["due_date"] = due
    uid = current_user_id()
    
    if kind == "deadline" and due:
        query("INSERT INTO deadlines (user_id, title, category, due_date, status, priority, notes) "
              "VALUES (%s,%s,'general',%s,'open',3,%s)",
              (uid, title, due, f"From doc: {e['filename']}"), commit=True)
    elif kind == "bill" and p.get("amount") is not None:
        query("INSERT INTO bills (user_id, name, amount, frequency, category, notes) "
              "VALUES (%s,%s,%s,'monthly','other',%s)",
              (uid, title, p["amount"], f"From doc: {e['filename']}"), commit=True)
    elif kind == "subscription" and p.get("amount") is not None:
        query("INSERT INTO subscriptions (user_id, name, amount, billing_cycle, notes) "
              "VALUES (%s,%s,%s,'monthly',%s)",
              (uid, title, p["amount"], f"From doc: {e['filename']}"), commit=True)
    else:
        return {"error": f"cannot apply '{kind}' without required fields; dismiss instead"}
        
    query("UPDATE document_extractions SET status='approved' WHERE id=%s", (ext_id,), commit=True)
    return {"status": "approved", "applied_as": kind}
