"""Calendar endpoints: connect (Google device-code), sync, and review extractions."""
from fastapi import APIRouter, HTTPException

from app.db.session import query
from app.services import crypto, calendar_ingest, calendar_google

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.post("/{account_id}/connect/start")
def connect_start(account_id: str):
    """Begin Google device-code auth; returns a code the user enters at the verification URL."""
    if not query("SELECT 1 FROM calendar_accounts WHERE id=%s", (account_id,)):
        raise HTTPException(404, "account not found")
    try:
        d = calendar_google.device_start()
    except calendar_google.GoogleError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "user_code": d["user_code"],
        "verification_url": d.get("verification_url", "https://google.com/device"),
        "device_code": d["device_code"],
        "interval": d.get("interval", 5),
        "expires_in": d.get("expires_in", 1800),
    }


@router.post("/{account_id}/connect/complete")
def connect_complete(account_id: str, payload: dict):
    """Poll once for the device-code token; store the refresh token when authorized."""
    dc = (payload or {}).get("device_code", "")
    if not dc:
        raise HTTPException(400, "device_code required")
    if not query("SELECT 1 FROM calendar_accounts WHERE id=%s", (account_id,)):
        raise HTTPException(404, "account not found")
    res = calendar_google.device_poll(dc)
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
    query("UPDATE calendar_accounts SET secret_enc=%s, status='connected', last_error=NULL WHERE id=%s",
          (enc, account_id), commit=True)
    return {"status": "connected"}


@router.post("/{account_id}/disconnect")
def disconnect(account_id: str):
    query("UPDATE calendar_accounts SET secret_enc=NULL, status='not_connected' WHERE id=%s",
          (account_id,), commit=True)
    return {"status": "not_connected"}


@router.post("/{account_id}/sync")
def sync(account_id: str):
    r = calendar_ingest.sync_account(account_id)
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return r


@router.get("/extractions")
def extractions(status: str = "pending"):
    return query(
        "SELECT x.*, a.email AS account_email FROM calendar_extractions x "
        "LEFT JOIN calendar_accounts a ON a.id = x.account_id "
        "WHERE x.status = %s ORDER BY x.event_date ASC LIMIT 200",
        (status,),
    )


@router.post("/extractions/{ext_id}/approve")
def approve(ext_id: str):
    r = calendar_ingest.approve_extraction(ext_id)
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return r


@router.post("/extractions/{ext_id}/dismiss")
def dismiss(ext_id: str):
    query("UPDATE calendar_extractions SET status='dismissed' WHERE id=%s", (ext_id,), commit=True)
    return {"status": "dismissed"}
