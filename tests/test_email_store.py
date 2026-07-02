"""Email persistence: dedup, queue, and apply-on-approval into the right table."""
from app.services import email_store
from conftest import patch_query


def _is_select(sql):
    return sql.strip().upper().startswith("SELECT")


def test_already_queued(monkeypatch):
    patch_query(monkeypatch, "app.services.email_store", [[{"?": 1}]])
    assert email_store.already_queued("acct", "uid-1") is True
    patch_query(monkeypatch, "app.services.email_store", [[]])
    assert email_store.already_queued("acct", "uid-2") is False


def test_process_msg_dedup_skips(monkeypatch):
    patch_query(monkeypatch, "app.services.email_store",
                lambda sql, p=(), c=False: [{"?": 1}] if _is_select(sql) else [])

    def _no_extract(*a):
        raise AssertionError("extract must not run when the message is already queued")

    monkeypatch.setattr(email_store, "extract", _no_extract)
    assert email_store.process_msg("a", "1", None, "s", "subj", "body") == (0, 0)


def test_process_msg_no_actionable_item(monkeypatch):
    patch_query(monkeypatch, "app.services.email_store",
                lambda sql, p=(), c=False: [] if _is_select(sql) else [])
    monkeypatch.setattr(email_store, "extract", lambda *a: None)
    assert email_store.process_msg("a", "1", None, "s", "subj", "body") == (1, 0)


def test_process_msg_queues_item(monkeypatch):
    fake = patch_query(monkeypatch, "app.services.email_store",
                       lambda sql, p=(), c=False: [] if _is_select(sql) else [])
    monkeypatch.setattr(email_store, "extract",
                        lambda *a: {"kind": "bill", "amount": 12.0, "summary": "s"})
    assert email_store.process_msg("a", "1", None, "s", "subj", "body") == (1, 1)
    assert any(sql.strip().startswith("INSERT") for sql, _, _ in fake.calls)


def test_approve_deadline(monkeypatch):
    row = {"id": "x", "kind": "deadline", "subject": "Renew", "sender": "dmv@x",
           "payload": {"title": "Renew plates", "due_date": "2030-01-01"}}
    seen = []

    def q(sql, p=(), c=False):
        seen.append(sql)
        if "FROM email_extractions" in sql and sql.strip().startswith("SELECT"):
            return [row]
        return []

    patch_query(monkeypatch, "app.services.email_store", q)
    out = email_store.approve_extraction("x")
    assert out == {"status": "approved", "applied_as": "deadline"}
    assert any("INSERT INTO deadlines" in s for s in seen)


def test_approve_bill(monkeypatch):
    row = {"id": "x", "kind": "bill", "subject": "Bill", "sender": "co",
           "payload": {"title": "Internet", "amount": 60}}
    patch_query(monkeypatch, "app.services.email_store",
                lambda sql, p=(), c=False: [row] if "SELECT" in sql and "email_extractions" in sql else [])
    assert email_store.approve_extraction("x")["applied_as"] == "bill"


def test_approve_deadline_without_date_is_rejected(monkeypatch):
    row = {"id": "x", "kind": "deadline", "subject": "S", "sender": "co",
           "payload": {"title": "no date"}}
    patch_query(monkeypatch, "app.services.email_store",
                lambda sql, p=(), c=False: [row] if "SELECT" in sql and "email_extractions" in sql else [])
    assert "error" in email_store.approve_extraction("x")


def test_approve_missing_row(monkeypatch):
    patch_query(monkeypatch, "app.services.email_store", [[]])
    assert email_store.approve_extraction("nope") == {"error": "not found"}
