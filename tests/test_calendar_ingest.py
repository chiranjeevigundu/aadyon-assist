"""Unit tests for the calendar ingestion and extraction flow."""
from app.services import calendar_ingest, calendar_extract
from conftest import patch_query


def test_normalize_valid_deadline():
    raw = {"kind": "deadline", "title": "Doctor Appt", "due_date": "2050-01-15", "amount": None}
    norm = calendar_extract.normalize(raw)
    assert norm["kind"] == "deadline"
    assert norm["due_date"] == "2050-01-15"


def test_normalize_past_deadline_dropped():
    raw = {"kind": "deadline", "title": "Old Appt", "due_date": "2020-01-15", "amount": None}
    assert calendar_extract.normalize(raw) is None


def test_normalize_none_dropped():
    raw = {"kind": "none", "title": "Flight to NY", "due_date": "2050-01-15"}
    assert calendar_extract.normalize(raw) is None


def test_account_not_found(monkeypatch):
    patch_query(monkeypatch, "app.services.calendar_ingest", [[]])
    assert calendar_ingest.sync_account("x") == {"error": "account not found"}


def test_account_not_connected(monkeypatch):
    patch_query(monkeypatch, "app.services.calendar_ingest",
                [[{"id": "a", "secret_enc": None}]])
    assert calendar_ingest.sync_account("a") == {"error": "account not connected"}


def test_sync_all_aggregates(monkeypatch):
    monkeypatch.setattr(calendar_ingest, "active_user_ids", lambda: ["u1"])
    monkeypatch.setattr(calendar_ingest, "set_current_user", lambda uid: None)
    patch_query(monkeypatch, "app.services.calendar_ingest",
                [[{"id": "a"}, {"id": "b"}]])
    monkeypatch.setattr(calendar_ingest, "sync_account",
                        lambda aid: {"queued": 3})
    out = calendar_ingest.sync_all()
    assert out == {"users": 1, "accounts": 2, "queued": 6}
