"""Read-model aggregation for the dashboard summary view."""
from app.db.session import query


def dashboard_summary() -> dict:
    """Everything the dashboard needs in one call."""
    deadlines = query(
        "SELECT *, (due_date - CURRENT_DATE) AS days_left FROM deadlines "
        "WHERE status <> 'done' ORDER BY due_date ASC"
    )
    debts = query("SELECT * FROM debt_summary")
    totals = query(
        """
        SELECT
          COALESCE(SUM(balance), 0)                  AS total_debt,
          COALESCE(SUM(min_payment), 0)              AS total_min_payments,
          COALESCE(SUM(balance * apr / 100), 0)      AS est_annual_interest,
          COALESCE(SUM(balance * apr / 100 / 12), 0) AS est_monthly_interest
        FROM debts
        """
    )[0]
    bills = query("SELECT * FROM bills WHERE active ORDER BY due_day NULLS LAST")
    subscriptions = query("SELECT * FROM subscriptions WHERE active ORDER BY renews_on NULLS LAST")
    shifts = query("SELECT * FROM shifts ORDER BY shift_date DESC LIMIT 20")
    return {
        "deadlines": deadlines,
        "debts": debts,
        "debt_totals": totals,
        "bills": bills,
        "subscriptions": subscriptions,
        "shifts": shifts,
    }
