"""Bank endpoints: connect (generic api key), sync, and review queue."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID

from app.db.session import query
from app.services import crypto, bank_ingest

router = APIRouter(prefix="/api/bank", tags=["bank"])

class ConnectPayload(BaseModel):
    api_key: str

@router.post("/{account_id}/connect")
def connect(account_id: UUID, payload: ConnectPayload):
    """Store the API key (secret_enc) for the bank account."""
    if not payload.api_key:
        raise HTTPException(400, "api_key is required")
        
    if not query("SELECT 1 FROM bank_accounts WHERE id=%s", (str(account_id),)):
        raise HTTPException(404, "account not found")
        
    try:
        enc = crypto.encrypt(payload.api_key)
    except crypto.CryptoError as e:
        raise HTTPException(400, str(e)) from e
        
    query("UPDATE bank_accounts SET secret_enc=%s, status='connected', last_error=NULL WHERE id=%s",
          (enc, str(account_id)), commit=True)
    return {"status": "connected"}


@router.post("/{account_id}/disconnect")
def disconnect(account_id: UUID):
    query("UPDATE bank_accounts SET secret_enc=NULL, status='not_connected' WHERE id=%s",
          (str(account_id),), commit=True)
    return {"status": "not_connected"}


@router.post("/{account_id}/sync")
def sync(account_id: UUID):
    r = bank_ingest.sync_account(str(account_id))
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return r


@router.get("/transactions")
def transactions(status: str = "pending"):
    return query(
        "SELECT x.*, a.institution AS account_institution FROM bank_transactions x "
        "LEFT JOIN bank_accounts a ON a.id = x.account_id "
        "WHERE x.status = %s ORDER BY x.date DESC LIMIT 200",
        (status,),
    )


@router.post("/transactions/{txn_id}/approve")
def approve(txn_id: UUID):
    r = bank_ingest.approve_transaction(str(txn_id))
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return r


@router.post("/transactions/{txn_id}/dismiss")
def dismiss(txn_id: UUID):
    query("UPDATE bank_transactions SET status='dismissed' WHERE id=%s", (str(txn_id),), commit=True)
    return {"status": "dismissed"}
