"""Tests for drive ingest."""
from app.services import drive_ingest


def test_sync_account_not_found(monkeypatch):
    from conftest import patch_query
    patch_query(monkeypatch, "app.services.drive_ingest", [[]])
    r = drive_ingest.sync_account("123")
    assert r["error"] == "account not found"


def test_sync_account_success(monkeypatch):
    from conftest import patch_query
    import datetime

    # Mock DB queries
    def mock_query(sql, params=(), commit=False):
        if "SELECT * FROM drive_accounts" in sql:
            return [{"id": "a", "secret_enc": "enc_token", "last_sync": datetime.datetime(2026, 7, 2, tzinfo=datetime.timezone.utc)}]
        return []
        
    fake = patch_query(monkeypatch, "app.services.drive_ingest", mock_query)
    monkeypatch.setattr("app.services.drive_store.query", fake)

    # Mock crypto
    monkeypatch.setattr("app.services.drive_ingest.crypto.decrypt", lambda x: "dec_token")
    monkeypatch.setattr("app.services.drive_ingest.crypto.encrypt", lambda x: "enc_token")
    
    # Mock drive_google methods imported into drive_ingest
    monkeypatch.setattr("app.services.drive_ingest.refresh", lambda x: {"access_token": "acc", "refresh_token": "dec_token"})
    monkeypatch.setattr("app.services.drive_ingest.fetch_files", lambda token, since_iso=None: [
        {"id": "f1", "name": "Doc", "mimeType": "application/pdf"}
    ])
    
    # Mock session
    monkeypatch.setattr("app.services.drive_store.current_user_id", lambda: "uid")
    
    r = drive_ingest.sync_account("a")
    assert r["scanned"] == 1
    assert r["queued"] == 1
    
    # Verify the file was inserted
    inserts = [c for c in fake.calls if c[0].strip().startswith("INSERT INTO drive_files")]
    assert len(inserts) == 1
    assert "f1" in inserts[0][1]
    assert "Doc" in inserts[0][1]
