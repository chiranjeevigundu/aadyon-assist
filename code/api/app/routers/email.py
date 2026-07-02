"""Email endpoints: connect (encrypt app-password), sync, and review extractions."""
from fastapi import APIRouter, HTTPException
from uuid import UUID
from app.db.session import query
from app.services import crypto, email_ingest, ms_graph

router = APIRouter(prefix="/api/email", tags=["email"])


@router.post("/{account_id}/connect")
def connect(account_id: UUID, payload: dict):
    pwd = (payload or {}).get("password", "").strip()
    if not pwd:
        raise HTTPException(400, "password required")
    rows = query("SELECT * FROM email_accounts WHERE id = %s", (str(account_id),))
    if not rows:
        raise HTTPException(404, "account not found")
    acct = rows[0]
    host = acct.get("imap_host") or "imap.mail.me.com"
    port = acct.get("imap_port") or 993
    # 1) verify the credentials actually work
    try:
        email_ingest.test_login(host, port, acct["email"], pwd)
    except Exception as e:  # noqa: BLE001
        query("UPDATE email_accounts SET status='error', last_error=%s WHERE id=%s",
              (f"login failed: {e}", str(account_id)), commit=True)
        raise HTTPException(400, f"IMAP login failed: {e}") from e
    # 2) encrypt + store
    try:
        enc = crypto.encrypt(pwd)
    except crypto.CryptoError as e:
        raise HTTPException(400, str(e)) from e
    query("UPDATE email_accounts SET secret_enc=%s, status='connected', last_error=NULL "
          "WHERE id=%s", (enc, str(account_id)), commit=True)
    return {"status": "connected"}


@router.post("/{account_id}/disconnect")
def disconnect(account_id: UUID):
    query("UPDATE email_accounts SET secret_enc=NULL, status='not_connected' WHERE id=%s",
          (str(account_id),), commit=True)
    return {"status": "not_connected"}


@router.post("/{account_id}/ms/start")
def ms_start(account_id: UUID):
    """Begin Microsoft device-code auth; returns a code the user enters at the verification URL."""
    if not query("SELECT 1 FROM email_accounts WHERE id=%s", (str(account_id),)):
        raise HTTPException(404, "account not found")
    try:
        d = ms_graph.device_start()
    except ms_graph.GraphError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "user_code": d["user_code"],
        "verification_uri": d.get("verification_uri", "https://microsoft.com/devicelogin"),
        "device_code": d["device_code"],
        "interval": d.get("interval", 5),
        "expires_in": d.get("expires_in", 900),
    }


@router.post("/{account_id}/ms/complete")
def ms_complete(account_id: UUID, payload: dict):
    """Poll once for the device-code token; store the refresh token when authorized."""
    dc = (payload or {}).get("device_code", "")
    if not dc:
        raise HTTPException(400, "device_code required")
    if not query("SELECT 1 FROM email_accounts WHERE id=%s", (str(account_id),)):
        raise HTTPException(404, "account not found")
    res = ms_graph.device_poll(dc)
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
    query("UPDATE email_accounts SET secret_enc=%s, status='connected', last_error=NULL WHERE id=%s",
          (enc, str(account_id)), commit=True)
    return {"status": "connected"}


@router.post("/{account_id}/sync")
def sync(account_id: UUID):
    r = email_ingest.sync_account(str(account_id))
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return r


@router.get("/extractions")
def extractions(status: str = "pending"):
    return query(
        "SELECT x.*, a.email AS account_email FROM email_extractions x "
        "LEFT JOIN email_accounts a ON a.id = x.account_id "
        "WHERE x.status = %s ORDER BY x.message_date DESC NULLS LAST LIMIT 200",
        (status,),
    )


@router.post("/extractions/{ext_id}/approve")
def approve(ext_id: UUID):
    r = email_ingest.approve_extraction(str(ext_id))
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return r


@router.post("/extractions/{ext_id}/dismiss")
def dismiss(ext_id: UUID):
    query("UPDATE email_extractions SET status='dismissed' WHERE id=%s", (str(ext_id),), commit=True)
    return {"status": "dismissed"}
