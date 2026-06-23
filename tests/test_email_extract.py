"""Unit tests for email extraction normalization (pure, no DB / no network)."""
from datetime import date, timedelta

from app.services.email_extract import coerce_due, normalize

FUTURE = (date.today() + timedelta(days=30)).isoformat()
PAST = (date.today() - timedelta(days=30)).isoformat()


def test_coerce_due_handles_stringly_null():
    for v in ("null", "none", "", "N/A", "tbd", None):
        assert coerce_due(v) is None


def test_coerce_due_validates_and_trims_iso():
    assert coerce_due(FUTURE) == FUTURE
    assert coerce_due(f"{FUTURE}T10:00:00Z") == FUTURE
    assert coerce_due("not-a-date") is None


def test_normalize_deadline_requires_future_date():
    assert normalize({"kind": "deadline", "due_date": FUTURE}) is not None
    assert normalize({"kind": "deadline", "due_date": PAST}) is None
    assert normalize({"kind": "deadline", "due_date": None}) is None


def test_normalize_bill_requires_positive_amount():
    assert normalize({"kind": "bill", "amount": 12.5}) is not None
    assert normalize({"kind": "bill", "amount": 0}) is None
    assert normalize({"kind": "bill", "amount": None}) is None


def test_normalize_coerces_currency_string():
    out = normalize({"kind": "subscription", "amount": "$1,234.50"})
    assert out is not None and out["amount"] == 1234.50


def test_normalize_drops_non_actionable():
    assert normalize({"kind": "none"}) is None
    assert normalize({"kind": "info"}) is None
