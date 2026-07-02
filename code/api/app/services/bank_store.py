"""Persistence for bank transactions."""
from app.db.session import current_user_id, query

def process_transaction(
    account_id: str,
    transaction_id: str,
    dt_str: str,
    amount: float,
    merchant: str,
    category: str
) -> tuple[int, int]:
    """Store a transaction in the review queue.
    
    Returns (scanned, queued_new).
    """
    uid = current_user_id()
    
    existing = query(
        "SELECT id FROM bank_transactions WHERE account_id=%s AND transaction_id=%s",
        (account_id, transaction_id)
    )
    if existing:
        return 1, 0
        
    query(
        "INSERT INTO bank_transactions "
        "(user_id, account_id, transaction_id, date, amount, merchant, category, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')",
        (uid, account_id, transaction_id, dt_str, amount, merchant, category),
        commit=True
    )
    return 1, 1

def approve_transaction(transaction_id: str) -> dict:
    """Mark a transaction as approved."""
    rows = query(
        "UPDATE bank_transactions SET status='approved' WHERE id=%s RETURNING id",
        (transaction_id,), commit=True
    )
    if not rows:
        return {"error": "transaction not found"}
    return {"status": "approved", "transaction_id": str(rows[0]["id"])}
