"""Microsoft Graph (Outlook / Microsoft 365) sync path.

Cursor = last_sync timestamp. Read-only (Mail.Read). Mints an access token from
the stored refresh token each sync; persists MS's rotated refresh token.
"""
from datetime import timezone

from app.db.session import query
from app.services import crypto, ms_graph
from app.services.email_store import process_msg
from app.services.llm import LLMError


def sync_graph(account_id: str, acct: dict, s) -> dict:
    """Fetch new Graph mail for one account, extract, queue pending items.

    `s` is the settings object (email_max_messages).
    """
    msgs = []
    try:
        rt = crypto.decrypt(acct["secret_enc"])
        tok = ms_graph.refresh(rt)
        if tok["refresh_token"] != rt:  # MS rotates refresh tokens
            query("UPDATE email_accounts SET secret_enc=%s WHERE id=%s",
                  (crypto.encrypt(tok["refresh_token"]), account_id), commit=True)
        since = acct.get("last_sync")
        since_iso = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if since else None
        msgs = ms_graph.fetch_messages(tok["access_token"], since_iso, top=s.email_max_messages)
        scanned = found = 0
        for mm in msgs:
            frm = (((mm.get("from") or {}).get("emailAddress") or {}).get("address") or "")
            sc, fo = process_msg(account_id, mm.get("id"), mm.get("receivedDateTime"),
                                 frm, mm.get("subject", ""), mm.get("bodyPreview", ""))
            scanned += sc
            found += fo
    except LLMError as e:
        query("UPDATE email_accounts SET status='error', last_error=%s WHERE id=%s",
              (str(e), account_id), commit=True)
        return {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        query("UPDATE email_accounts SET status='error', last_error=%s WHERE id=%s",
              (str(e)[:300], account_id), commit=True)
        return {"error": f"{type(e).__name__}: {e}"}
    query("UPDATE email_accounts SET status='connected', last_sync=now(), last_error=NULL WHERE id=%s",
          (account_id,), commit=True)
    return {"in_window": len(msgs), "scanned": scanned, "queued": found}
