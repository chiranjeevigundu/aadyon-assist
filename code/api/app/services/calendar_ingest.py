"""Calendar ingest entrypoint.

Runs all accounts for the morning briefing.
Read-only: nothing is deleted or added to the calendar autonomously.
Extracted items land in calendar_extractions (status=pending) for human review.
"""
from datetime import datetime, timezone

from app.db.session import active_user_ids, query, set_current_user
from app.services import crypto
from app.services.calendar_google import fetch_events, refresh, GoogleError
from app.services.calendar_store import process_event, approve_extraction

__all__ = ["sync_account", "sync_all", "approve_extraction"]

def sync_account(account_id: str) -> dict:
    """Fetch recent events for one account, extract, queue pending items."""
    rows = query("SELECT * FROM calendar_accounts WHERE id = %s", (account_id,))
    if not rows:
        return {"error": "account not found"}
    acct = rows[0]
    if not acct.get("secret_enc"):
        return {"error": "account not connected"}
    
    try:
        refresh_token = crypto.decrypt(acct["secret_enc"])
        tokens = refresh(refresh_token)
        access_token = tokens["access_token"]
        # Update refresh token if it was rotated
        if tokens["refresh_token"] != refresh_token:
            enc = crypto.encrypt(tokens["refresh_token"])
            query("UPDATE calendar_accounts SET secret_enc=%s WHERE id=%s", (enc, account_id), commit=True)
    except Exception as e:  # noqa: BLE001
        query("UPDATE calendar_accounts SET status='error', last_error=%s WHERE id=%s",
              (f"token refresh failed: {e}", account_id), commit=True)
        return {"error": f"Token refresh failed: {e}"}

    # Fetch events since last_sync or fallback to now
    since = acct.get("last_sync")
    since_iso = since.isoformat() if since else datetime.now(timezone.utc).isoformat()
    
    try:
        events = fetch_events(access_token, since_iso=since_iso)
    except GoogleError as e:
        query("UPDATE calendar_accounts SET status='error', last_error=%s WHERE id=%s",
              (f"fetch failed: {e}", account_id), commit=True)
        return {"error": f"Fetch failed: {e}"}
        
    scanned = 0
    queued = 0
    for evt in events:
        evt_id = evt.get("id")
        title = evt.get("summary", "")
        desc = evt.get("description", "")
        
        # Determine event date: Google sends 'dateTime' for specific times, or 'date' for all-day events
        start = evt.get("start", {})
        dt = start.get("dateTime") or start.get("date")
        
        if not evt_id or not dt:
            continue
            
        s_inc, q_inc = process_event(account_id, evt_id, dt, title, desc)
        scanned += s_inc
        queued += q_inc

    query("UPDATE calendar_accounts SET last_sync=now(), status='connected', last_error=NULL WHERE id=%s",
          (account_id,), commit=True)

    return {"scanned": scanned, "queued": queued}


def sync_all() -> dict:
    """Sync every active user's connected calendars."""
    total = {"users": 0, "accounts": 0, "queued": 0}
    for uid in active_user_ids():
        set_current_user(uid)
        total["users"] += 1
        accts = query("SELECT id FROM calendar_accounts WHERE active AND secret_enc IS NOT NULL")
        for a in accts:
            r = sync_account(a["id"])
            total["accounts"] += 1
            total["queued"] += r.get("queued", 0)
    return total
