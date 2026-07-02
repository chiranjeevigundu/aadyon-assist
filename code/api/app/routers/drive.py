"""Drive endpoints: connect (Google device-code), sync, and list files."""
from fastapi import APIRouter, HTTPException
from uuid import UUID

from app.db.session import query
from app.services import crypto, drive_ingest, drive_google

router = APIRouter(prefix="/api/drive", tags=["drive"])


@router.post("/{account_id}/connect/start")
def connect_start(account_id: UUID):
    """Begin Google device-code auth; returns a code the user enters at the verification URL."""
    if not query("SELECT 1 FROM drive_accounts WHERE id=%s", (str(account_id),)):
        raise HTTPException(404, "account not found")
    try:
        d = drive_google.device_start()
    except drive_google.GoogleError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "user_code": d["user_code"],
        "verification_url": d.get("verification_url", "https://google.com/device"),
        "device_code": d["device_code"],
        "interval": d.get("interval", 5),
        "expires_in": d.get("expires_in", 1800),
    }


@router.post("/{account_id}/connect/complete")
def connect_complete(account_id: UUID, payload: dict):
    """Poll once for the device-code token; store the refresh token when authorized."""
    dc = (payload or {}).get("device_code", "")
    if not dc:
        raise HTTPException(400, "device_code required")
    if not query("SELECT 1 FROM drive_accounts WHERE id=%s", (str(account_id),)):
        raise HTTPException(404, "account not found")
    res = drive_google.device_poll(dc)
    if res.get("pending"):
        return {"status": "pending"}
    if res.get("error"):
        raise HTTPException(400, res["error"])
    rt = res.get("refresh_token")
    if not rt:
        raise HTTPException(400, "no refresh token returned")
    try:
        enc = crypto.encrypt(rt)
    except crypto.CryptoError as e:
        raise HTTPException(400, str(e)) from e
    query("UPDATE drive_accounts SET secret_enc=%s, status='connected', last_error=NULL WHERE id=%s",
          (enc, str(account_id)), commit=True)
    return {"status": "connected"}


@router.post("/{account_id}/disconnect")
def disconnect(account_id: UUID):
    query("UPDATE drive_accounts SET secret_enc=NULL, status='not_connected' WHERE id=%s",
          (str(account_id),), commit=True)
    return {"status": "not_connected"}


@router.post("/{account_id}/sync")
def sync(account_id: UUID):
    r = drive_ingest.sync_account(str(account_id))
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return r


@router.get("/files")
def files(status: str = "synced"):
    return query(
        "SELECT f.*, a.email AS account_email FROM drive_files f "
        "LEFT JOIN drive_accounts a ON a.id = f.account_id "
        "WHERE f.status = %s ORDER BY f.updated_at DESC LIMIT 200",
        (status,),
    )
