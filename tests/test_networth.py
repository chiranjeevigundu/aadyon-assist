"""Net worth read-model + snapshot, with the DB mocked (see conftest.patch_query)."""
from decimal import Decimal

from conftest import patch_query


def test_net_worth_summary_math(monkeypatch):
    from app.services import networth

    # query() is called in order: total_assets, total_liabilities, by_kind,
    # assets, debts, history. Feed each call's rows.
    patch_query(
        monkeypatch,
        "app.services.networth",
        [
            [{"t": Decimal("15000.00")}],                       # total_assets
            [{"t": Decimal("4000.00")}],                        # total_liabilities
            [{"kind": "cash", "total": Decimal("15000.00"), "n": 2}],  # by_kind
            [{"id": "a1", "name": "Checking", "kind": "cash", "value": Decimal("15000.00")}],  # assets
            [{"id": "d1", "name": "Card", "kind": "credit", "balance": Decimal("4000.00")}],   # debts
            [],                                                 # history
        ],
    )
    s = networth.net_worth_summary()
    assert s["total_assets"] == 15000.0
    assert s["total_liabilities"] == 4000.0
    assert s["net_worth"] == 11000.0          # assets − liabilities
    assert s["assets_by_kind"][0] == {"kind": "cash", "total": 15000.0, "count": 2}
    assert isinstance(s["net_worth"], float)  # Decimals coerced for JSON


def test_net_worth_negative_when_debts_exceed_assets(monkeypatch):
    from app.services import networth

    patch_query(
        monkeypatch,
        "app.services.networth",
        [
            [{"t": Decimal("1000")}],   # assets
            [{"t": Decimal("9000")}],   # liabilities
            [],                         # by_kind
            [],                         # assets
            [],                         # debts
            [],                         # history
        ],
    )
    s = networth.net_worth_summary()
    assert s["net_worth"] == -8000.0


def test_take_snapshot_upserts_today(monkeypatch):
    from app.services import networth

    # summary() makes 6 queries, then take_snapshot() makes the INSERT (7th).
    fake = patch_query(
        monkeypatch,
        "app.services.networth",
        [
            [{"t": Decimal("2000")}],   # assets
            [{"t": Decimal("500")}],    # liabilities
            [], [], [], [],             # by_kind, assets, debts, history
            [{"snapshot_date": "2026-08-09", "net_worth": Decimal("1500")}],  # INSERT ... RETURNING
        ],
    )
    monkeypatch.setattr(networth, "current_user_id", lambda: "u1")
    row = networth.take_snapshot()
    assert row["net_worth"] == Decimal("1500")
    # The last query is the upsert and it commits.
    sql, params, commit = fake.calls[-1]
    assert "INSERT INTO net_worth_snapshots" in sql
    assert "ON CONFLICT (user_id, snapshot_date) DO UPDATE" in sql
    assert commit is True
    assert params == ("u1", 2000.0, 500.0, 1500.0, "USD")
