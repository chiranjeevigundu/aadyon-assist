def test_sync_account_success(monkeypatch):
    from app.services import bank_ingest
    from conftest import patch_query
    import datetime

    # Mock DB queries
    def mock_query(sql, params=(), commit=False):
        if "SELECT * FROM bank_accounts" in sql:
            return [{"id": "b1", "secret_enc": "enc_token", "last_sync": datetime.datetime(2026, 7, 2, tzinfo=datetime.timezone.utc)}]
        return []

    fake = patch_query(monkeypatch, "app.services.bank_ingest", mock_query)
    monkeypatch.setattr("app.services.bank_store.query", fake)

    # Mock crypto
    monkeypatch.setattr("app.services.bank_ingest.crypto.decrypt", lambda x: "dec_token")
    monkeypatch.setattr("app.services.bank_ingest.crypto.encrypt", lambda x: "enc_token")
    
    # Mock bank_client methods imported into bank_ingest
    monkeypatch.setattr("app.services.bank_ingest.fetch_transactions", lambda token, since_iso=None: [
        {"transaction_id": "txn1", "date": "2026-07-02T10:00:00Z", "amount": -50.0, "merchant": "Uber", "category": "Transport"}
    ])

    # Mock session
    monkeypatch.setattr("app.services.bank_store.current_user_id", lambda: "uid")

    r = bank_ingest.sync_account("b1")
    assert r["scanned"] == 1
    assert r["queued"] == 1
    
    # Verify the insert query
    inserts = [c for c in fake.calls if "INSERT INTO bank_transactions" in c[0]]
    assert len(inserts) == 1
    assert inserts[0][1] == ("uid", "b1", "txn1", "2026-07-02T10:00:00Z", -50.0, "Uber", "Transport")


def test_approve_transaction(monkeypatch):
    from app.services import bank_store
    from conftest import patch_query

    patch_query(monkeypatch, "app.services.bank_store", lambda sql, p=(), c=False: [{"id": "txn1"}])
    r = bank_store.approve_transaction("txn1")
    assert r["status"] == "approved"
    assert r["transaction_id"] == "txn1"
