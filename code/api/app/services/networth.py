"""Net worth read-model + snapshotting.

Net worth = total assets − total liabilities. Assets are holdings in the `assets`
table; liabilities are the existing `debts`. All queries are RLS-scoped to the
current user via the shared `query` seam.
"""
from app.db.session import current_user_id, query


def _f(x) -> float:
    """Coerce a possibly-Decimal/None DB value to a plain float for JSON."""
    return float(x) if x is not None else 0.0


def net_worth_summary() -> dict:
    """Everything the Net Worth dashboard needs in one call: totals, the breakdown
    of assets by kind, the largest holdings/debts, and the snapshot history."""
    total_assets = _f(query("SELECT COALESCE(SUM(value), 0) AS t FROM assets WHERE active")[0]["t"])
    total_liabilities = _f(query("SELECT COALESCE(SUM(balance), 0) AS t FROM debts")[0]["t"])
    net = round(total_assets - total_liabilities, 2)

    by_kind = query(
        "SELECT kind, COALESCE(SUM(value), 0) AS total, COUNT(*) AS n "
        "FROM assets WHERE active GROUP BY kind ORDER BY total DESC"
    )
    assets = query(
        "SELECT id, name, kind, institution, value, currency, as_of "
        "FROM assets WHERE active ORDER BY value DESC LIMIT 100"
    )
    debts = query(
        "SELECT id, name, kind, balance, apr, min_payment "
        "FROM debts ORDER BY balance DESC LIMIT 100"
    )
    history = query(
        "SELECT snapshot_date, total_assets, total_liabilities, net_worth "
        "FROM net_worth_snapshots ORDER BY snapshot_date ASC LIMIT 366"
    )
    return {
        "currency": "USD",
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "net_worth": net,
        "assets_by_kind": [
            {"kind": r["kind"], "total": _f(r["total"]), "count": r["n"]} for r in by_kind
        ],
        "assets": assets,
        "debts": debts,
        "history": history,
    }


def take_snapshot() -> dict:
    """Record today's net worth (idempotent per day — re-running overwrites today).

    Returns the stored snapshot row."""
    s = net_worth_summary()
    rows = query(
        "INSERT INTO net_worth_snapshots "
        "  (user_id, snapshot_date, total_assets, total_liabilities, net_worth, currency) "
        "VALUES (%s, CURRENT_DATE, %s, %s, %s, %s) "
        "ON CONFLICT (user_id, snapshot_date) DO UPDATE SET "
        "  total_assets = EXCLUDED.total_assets, "
        "  total_liabilities = EXCLUDED.total_liabilities, "
        "  net_worth = EXCLUDED.net_worth, "
        "  currency = EXCLUDED.currency "
        "RETURNING snapshot_date, total_assets, total_liabilities, net_worth, currency",
        (current_user_id(), s["total_assets"], s["total_liabilities"], s["net_worth"], s["currency"]),
        commit=True,
    )
    return rows[0]
