"""Email ingest entrypoint: per-account dispatch (IMAP vs Graph) + sync_all."""
from app.services import email_ingest
from conftest import patch_query


def test_account_not_found(monkeypatch):
    patch_query(monkeypatch, "app.services.email_ingest", [[]])
    assert email_ingest.sync_account("x") == {"error": "account not found"}


def test_account_not_connected(monkeypatch):
    patch_query(monkeypatch, "app.services.email_ingest",
                [[{"id": "a", "secret_enc": None}]])
    assert email_ingest.sync_account("a") == {"error": "account not connected"}


def test_dispatch_to_graph(monkeypatch):
    patch_query(monkeypatch, "app.services.email_ingest",
                [[{"id": "a", "secret_enc": "enc", "auth_type": "oauth_microsoft"}]])
    monkeypatch.setattr(email_ingest, "sync_graph",
                        lambda aid, acct, s: {"via": "graph", "id": aid})
    assert email_ingest.sync_account("a") == {"via": "graph", "id": "a"}


def test_dispatch_to_imap(monkeypatch):
    patch_query(monkeypatch, "app.services.email_ingest",
                [[{"id": "a", "secret_enc": "enc", "auth_type": "imap"}]])
    monkeypatch.setattr(email_ingest, "sync_imap",
                        lambda aid, acct, s: {"via": "imap", "id": aid})
    assert email_ingest.sync_account("a") == {"via": "imap", "id": "a"}


def test_sync_all_aggregates(monkeypatch):
    patch_query(monkeypatch, "app.services.email_ingest",
                [[{"id": "a"}, {"id": "b"}]])
    monkeypatch.setattr(email_ingest, "sync_account",
                        lambda aid: {"queued": 2})
    out = email_ingest.sync_all()
    assert out == {"accounts": 2, "queued": 4}
