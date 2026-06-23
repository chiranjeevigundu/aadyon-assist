"""Email ingest entrypoint.

Dispatches each account to the right provider path (IMAP or Microsoft Graph),
runs all accounts for the morning briefing, and re-exports the review helpers.
Read-only: nothing is deleted or sent. Extracted items land in email_extractions
(status=pending) for human review on the Accounts page.

The implementation is split across cohesive modules:
  email_extract — LLM extraction + output normalization
  email_store   — dedup, queue pending items, apply approved ones
  email_imap    — IMAP reading + iCloud/Gmail sync path
  email_graph   — Microsoft Graph (Outlook/365) sync path
"""
from app.core.config import get_settings
from app.db.session import query
from app.services.email_graph import sync_graph
from app.services.email_imap import sync_imap, test_login  # noqa: F401 (re-export)
from app.services.email_store import approve_extraction     # noqa: F401 (re-export)

__all__ = ["sync_account", "sync_all", "approve_extraction", "test_login"]


def sync_account(account_id: str) -> dict:
    """Fetch recent mail for one account, extract, queue pending items."""
    s = get_settings()
    rows = query("SELECT * FROM email_accounts WHERE id = %s", (account_id,))
    if not rows:
        return {"error": "account not found"}
    acct = rows[0]
    if not acct.get("secret_enc"):
        return {"error": "account not connected"}
    if acct.get("auth_type") == "oauth_microsoft":
        return sync_graph(account_id, acct, s)
    return sync_imap(account_id, acct, s)


def sync_all() -> dict:
    accts = query("SELECT id FROM email_accounts WHERE active AND secret_enc IS NOT NULL")
    total = {"accounts": 0, "queued": 0}
    for a in accts:
        r = sync_account(a["id"])
        total["accounts"] += 1
        total["queued"] += r.get("queued", 0)
    return total
