"""Drive ingest entrypoint.

Runs all accounts to sync recent files.
Read-only: nothing is deleted or added to the drive autonomously.
"""


from app.db.session import active_user_ids, query, set_current_user
from app.services import crypto
from app.services.drive_google import fetch_files, refresh, GoogleError
from app.services.drive_store import process_file

__all__ = ["sync_account", "sync_all"]

def sync_account(account_id: str) -> dict:
    """Fetch recent files for one account, extract, queue pending items."""
    rows = query("SELECT * FROM drive_accounts WHERE id = %s", (account_id,))
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
            query("UPDATE drive_accounts SET secret_enc=%s WHERE id=%s", (enc, account_id), commit=True)
    except Exception as e:  # noqa: BLE001
        query("UPDATE drive_accounts SET status='error', last_error=%s WHERE id=%s",
              (f"token refresh failed: {e}", account_id), commit=True)
        return {"error": f"Token refresh failed: {e}"}

    # Fetch files since last_sync (or all files if None)
    since = acct.get("last_sync")
    since_iso = since.isoformat() if since else None
    
    try:
        files = fetch_files(access_token, since_iso=since_iso)
    except GoogleError as e:
        query("UPDATE drive_accounts SET status='error', last_error=%s WHERE id=%s",
              (f"fetch failed: {e}", account_id), commit=True)
        return {"error": f"Fetch failed: {e}"}
        
    scanned = 0
    queued = 0
    for f in files:
        s_inc, q_inc = process_file(account_id, f)
        scanned += s_inc
        queued += q_inc

    query("UPDATE drive_accounts SET last_sync=now(), status='connected', last_error=NULL WHERE id=%s",
          (account_id,), commit=True)

    return {"scanned": scanned, "queued": queued}


def sync_all() -> dict:
    """Sync every active user's connected drives."""
    total = {"users": 0, "accounts": 0, "queued": 0}
    for uid in active_user_ids():
        set_current_user(uid)
        total["users"] += 1
        accts = query("SELECT id FROM drive_accounts WHERE active AND secret_enc IS NOT NULL")
        for a in accts:
            r = sync_account(a["id"])
            total["accounts"] += 1
            total["queued"] += r.get("queued", 0)
    return total
