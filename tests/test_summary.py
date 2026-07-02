"""Tracker summary aggregation returns every section in one payload (DB mocked)."""
from app.services import summary
from conftest import patch_query


def test_dashboard_summary_shape(monkeypatch):
    def q(sql, p=(), c=False):
        if "FROM deadlines" in sql:
            return [{"title": "Rent", "days_left": 5}]
        if "debt_summary" in sql:
            return [{"name": "Visa card", "utilization_pct": 30}]
        if "FROM debts" in sql:               # the SUM(...) totals query
            return [{"total_debt": 1000, "total_min_payments": 50,
                     "est_annual_interest": 200, "est_monthly_interest": 16}]
        if "FROM bills" in sql:
            return [{"name": "Internet", "amount": 60}]
        if "FROM subscriptions" in sql:
            return [{"name": "Spotify", "amount": 11}]
        if "FROM shifts" in sql:
            return [{"employer": "Cafe"}]
        return []

    patch_query(monkeypatch, "app.services.summary", q)
    out = summary.dashboard_summary()
    assert set(out) == {"deadlines", "debts", "debt_totals", "bills", "subscriptions", "shifts"}
    assert out["debt_totals"]["total_debt"] == 1000
    assert out["deadlines"][0]["title"] == "Rent"
    assert out["bills"][0]["name"] == "Internet"
