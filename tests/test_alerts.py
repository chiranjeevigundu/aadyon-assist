"""Proactive alerts: deadline windowing, bill due-day math, severity ordering."""
from datetime import date

from app.services import alerts
from conftest import patch_query

TODAY = date(2026, 7, 2)


def _q(deadlines, bills):
    def handler(sql, p=(), c=False):
        if "FROM deadlines" in sql:
            return deadlines
        if "FROM bills" in sql:
            return bills
        return []
    return handler


def test_overdue_deadline_is_high_and_first(monkeypatch):
    patch_query(monkeypatch, "app.services.alerts", _q(
        [{"id": "d1", "title": "File form", "due_date": date(2026, 6, 30), "status": "open"},
         {"id": "d2", "title": "Renew card", "due_date": date(2026, 7, 4), "status": "open"}],
        [],
    ))
    out = alerts.build_alerts(days=3, today=TODAY)
    assert [a["id"] for a in out] == ["d1", "d2"]
    assert out[0]["severity"] == "high" and out[0]["when"] == "2d overdue"
    assert out[1]["severity"] == "medium" and out[1]["when"] == "due in 2d"


def test_bill_due_day_wraps_to_next_month(monkeypatch):
    # due_day=1 on July 2 -> next due Aug 1, outside a 3-day window.
    patch_query(monkeypatch, "app.services.alerts", _q(
        [], [{"id": "b1", "name": "Rent", "amount": 1200, "due_day": 1, "autopay": False}],
    ))
    assert alerts.build_alerts(days=3, today=TODAY) == []


def test_bill_within_window_autopay_lowers_severity(monkeypatch):
    patch_query(monkeypatch, "app.services.alerts", _q(
        [], [{"id": "b1", "name": "Power", "amount": 80, "due_day": 4, "autopay": True},
             {"id": "b2", "name": "Card min", "amount": 35, "due_day": 3, "autopay": False}],
    ))
    out = alerts.build_alerts(days=3, today=TODAY)
    assert [a["id"] for a in out] == ["b2", "b1"]        # high before medium
    assert out[0]["severity"] == "high"
    assert out[1]["severity"] == "medium"


def test_due_today(monkeypatch):
    patch_query(monkeypatch, "app.services.alerts", _q(
        [{"id": "d1", "title": "Pay fee", "due_date": TODAY, "status": "open"}], [],
    ))
    out = alerts.build_alerts(days=3, today=TODAY)
    assert out[0]["when"] == "due today" and out[0]["severity"] == "high"


def test_markdown_is_ascii_safe(monkeypatch):
    patch_query(monkeypatch, "app.services.alerts", _q(
        [{"id": "d1", "title": "Pay fee", "due_date": TODAY, "status": "open"}], [],
    ))
    md = alerts.alerts_markdown(alerts.build_alerts(days=3, today=TODAY))
    assert "Pay fee" in md
    md.encode("latin-1")  # ntfy headers/body path must not smuggle non-latin text


def test_next_due_clamps_day_29_plus():
    # due_day 31 in a 30-day month must not raise.
    assert alerts._next_due(31, date(2026, 6, 15)) == date(2026, 6, 28)
