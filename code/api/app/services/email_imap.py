"""IMAP mail reading (read-only) and the IMAP sync path.

Used for iCloud and Gmail (app-password accounts). Never deletes or sends.
Uses a UID high-water mark (+ UIDVALIDITY) so each sync only reads new mail.
"""
import email
import imaplib
import re
from datetime import date, datetime, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime

from app.db.session import query
from app.services import crypto
from app.services.email_extract import extract
from app.services.email_store import already_queued, insert_extraction
from app.services.llm import LLMError


def dec(s) -> str:
    """Decode a possibly-encoded email header to str."""
    if not s:
        return ""
    out = []
    for part, enc in decode_header(s):
        out.append(part.decode(enc or "utf-8", "replace") if isinstance(part, bytes) else part)
    return "".join(out)


def plain_body(msg, limit: int = 800) -> str:
    """First text/plain part, truncated."""
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == "text/plain" and "attachment" not in str(p.get("Content-Disposition")):
                try:
                    return p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace")[:limit]
                except Exception:  # noqa: BLE001
                    continue
        return ""
    try:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")[:limit]
    except Exception:  # noqa: BLE001
        return ""


def test_login(host: str, port: int, user: str, password: str) -> None:
    """Raise on failure; return None on success."""
    m = imaplib.IMAP4_SSL(host, port or 993)
    try:
        m.login(user, password)
        m.select("INBOX", readonly=True)
    finally:
        try:
            m.logout()
        except Exception:  # noqa: BLE001
            pass


def uidvalidity(m) -> int | None:
    try:
        typ, d = m.status("INBOX", "(UIDVALIDITY)")
        mm = re.search(rb"UIDVALIDITY (\d+)", d[0] or b"")
        return int(mm.group(1)) if mm else None
    except Exception:  # noqa: BLE001
        return None


def sync_imap(account_id: str, acct: dict, s) -> dict:
    """Fetch new IMAP mail for one account, extract, queue pending items.

    `s` is the settings object (email_lookback_days, email_max_messages).
    """
    scanned = found = 0
    n_window = 0
    max_uid = int(acct.get("last_uid") or 0)
    validity = acct.get("uid_validity")
    m = None
    try:
        pwd = crypto.decrypt(acct["secret_enc"])
        host = acct.get("imap_host") or "imap.mail.me.com"
        port = acct.get("imap_port") or 993
        m = imaplib.IMAP4_SSL(host, port)
        m.login(acct["email"], pwd)
        m.select("INBOX", readonly=True)
        validity = uidvalidity(m)
        last_uid = int(acct.get("last_uid") or 0)
        if acct.get("uid_validity") is not None and validity != acct.get("uid_validity"):
            last_uid = 0  # mailbox reset (UIDVALIDITY changed) -> re-scan the window
        max_uid = last_uid
        since = (date.today() - timedelta(days=s.email_lookback_days)).strftime("%d-%b-%Y")
        typ, data = m.uid("search", None, "SINCE", since)  # unquoted date; iCloud-friendly
        all_uids = sorted(int(u) for u in (data[0].split() if data and data[0] else []))
        uids = [u for u in all_uids if u > last_uid][-s.email_max_messages:]  # only new mail
        n_window = len(uids)
        print(f"[email] {acct['email']}: {n_window} new message(s) past uid {last_uid}", flush=True)
        for uid_int in uids:
            uid_s = str(uid_int)
            if uid_int > max_uid:
                max_uid = uid_int   # advance high-water past every processed msg
            # Belt-and-suspenders dedup against already-queued items.
            if already_queued(account_id, uid_s):
                continue
            try:
                typ, mdata = m.uid("fetch", uid_s, "(BODY.PEEK[])")
                raw = next((p[1] for p in (mdata or []) if isinstance(p, tuple) and len(p) >= 2), None)
                if raw is None:
                    if scanned == 0:
                        print(f"[email] no body for uid {uid_s}: {repr(mdata)[:160]}", flush=True)
                    continue
                msg = email.message_from_bytes(raw)
                sender = dec(msg.get("From"))
                subject = dec(msg.get("Subject"))
                body = plain_body(msg)
                scanned += 1
                item = extract(sender, subject, body)
                if not item:
                    continue
                try:
                    mdate = parsedate_to_datetime(msg.get("Date"))
                except Exception:  # noqa: BLE001
                    mdate = datetime.now()
                insert_extraction(account_id, uid_s, mdate, sender, subject, item)
                found += 1
            except LLMError:
                raise
            except Exception as me:  # noqa: BLE001 — skip a bad message, keep going
                print(f"[email] skip uid {uid_s}: {me}", flush=True)
                continue
    except LLMError as e:
        query("UPDATE email_accounts SET status='error', last_error=%s WHERE id=%s",
              (str(e), account_id), commit=True)
        return {"error": str(e), "scanned": scanned}
    except imaplib.IMAP4.error as e:
        query("UPDATE email_accounts SET status='error', last_error=%s WHERE id=%s",
              (f"IMAP: {e}", account_id), commit=True)
        return {"error": f"IMAP error: {e}"}
    except Exception as e:  # noqa: BLE001 — never 500
        query("UPDATE email_accounts SET status='error', last_error=%s WHERE id=%s",
              (str(e)[:300], account_id), commit=True)
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        if m is not None:
            try:
                m.logout()
            except Exception:  # noqa: BLE001
                pass

    query("UPDATE email_accounts SET status='connected', last_sync=now(), last_error=NULL, "
          "last_uid=%s, uid_validity=%s WHERE id=%s",
          (max_uid, validity, account_id), commit=True)
    return {"in_window": n_window, "scanned": scanned, "queued": found, "last_uid": max_uid}
