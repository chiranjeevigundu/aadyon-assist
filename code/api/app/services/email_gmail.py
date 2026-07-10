"""Gmail (Google OAuth) sync path.

Window = email_lookback_days via Gmail's newer_than query; dedup by message id
in email_store. Read-only (gmail.readonly). Mints an access token from the
stored refresh token each sync (Google does not rotate refresh tokens).
"""
from app.db.session import query
from app.services import crypto, google_oauth
from app.services.email_store import process_msg
from app.services.llm import LLMError


def sync_gmail(account_id: str, acct: dict, s) -> dict:
    """Fetch new Gmail mail for one account, extract, queue pending items.

    `s` is the settings object (email_lookback_days, email_max_messages).
    """
    msgs = []
    try:
        rt = crypto.decrypt(acct["secret_enc"])
        tok = google_oauth.refresh(rt)
        msgs = google_oauth.fetch_messages(tok["access_token"], s.email_lookback_days,
                                           top=s.email_max_messages)
        scanned = found = 0
        for mm in msgs:
            sc, fo = process_msg(account_id, mm["id"], mm.get("date"),
                                 mm.get("from", ""), mm.get("subject", ""), mm.get("snippet", ""))
            scanned += sc
            found += fo
    except LLMError as e:
        query("UPDATE email_accounts SET status='error', last_error=%s WHERE id=%s",
              (str(e), account_id), commit=True)
        return {"error": str(e)}
    except Exception as e:  # noqa: BLE001 — never 500
        query("UPDATE email_accounts SET status='error', last_error=%s WHERE id=%s",
              (str(e)[:300], account_id), commit=True)
        return {"error": f"{type(e).__name__}: {e}"}
    query("UPDATE email_accounts SET status='connected', last_sync=now(), last_error=NULL WHERE id=%s",
          (account_id,), commit=True)
    return {"in_window": len(msgs), "scanned": scanned, "queued": found}
