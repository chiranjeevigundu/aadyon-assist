"""Bank ingest entrypoint.

Syncs bank transactions into the review queue.
Money movement is NEVER executed autonomously.
"""


from app.db.session import active_user_ids, query, set_current_user
from app.services import crypto
from app.services.bank_client import fetch_transactions, BankError
from app.services.bank_store import process_transaction, approve_transaction

__all__ = ["sync_account", "sync_all", "approve_transaction"]

def sync_account(account_id: str) -> dict:
    """Fetch recent transactions for one account, queue pending items."""
    rows = query("SELECT * FROM bank_accounts WHERE id = %s", (account_id,))
    if not rows:
        return {"error": "account not found"}
    acct = rows[0]
    if not acct.get("secret_enc"):
        return {"error": "account not connected"}
    
    try:
        api_key = crypto.decrypt(acct["secret_enc"])
    except Exception as e:  # noqa: BLE001
        query("UPDATE bank_accounts SET status='error', last_error=%s WHERE id=%s",
              (f"token decryption failed: {e}", account_id), commit=True)
        return {"error": f"Token decryption failed: {e}"}

    # Fetch transactions since last_sync or fallback to 30 days ago
    since = acct.get("last_sync")
    since_iso = since.isoformat() if since else None
    
    try:
        transactions = fetch_transactions(api_key, since_iso=since_iso)
    except BankError as e:
        query("UPDATE bank_accounts SET status='error', last_error=%s WHERE id=%s",
              (f"fetch failed: {e}", account_id), commit=True)
        return {"error": f"Fetch failed: {e}"}
        
    scanned = 0
    queued = 0
    for txn in transactions:
        txn_id = txn.get("transaction_id")
        dt = txn.get("date")
        amount = txn.get("amount", 0.0)
        merchant = txn.get("merchant", "")
        category = txn.get("category", "")
        
        if not txn_id or not dt:
            continue
            
        s_inc, q_inc = process_transaction(account_id, txn_id, dt, amount, merchant, category)
        scanned += s_inc
        queued += q_inc

    query("UPDATE bank_accounts SET last_sync=now(), status='connected', last_error=NULL WHERE id=%s",
          (account_id,), commit=True)

    return {"scanned": scanned, "queued": queued}


def sync_all() -> dict:
    """Sync every active user's connected bank accounts."""
    total = {"users": 0, "accounts": 0, "queued": 0}
    for uid in active_user_ids():
        set_current_user(uid)
        total["users"] += 1
        accts = query("SELECT id FROM bank_accounts WHERE active AND secret_enc IS NOT NULL")
        for a in accts:
            r = sync_account(a["id"])
            total["accounts"] += 1
            total["queued"] += r.get("queued", 0)
    return total
