import json

def test_analyze_document_pdf(monkeypatch, tmp_path):
    from app.services import document_ingest
    from conftest import patch_query

    # Create dummy pdf-like path (no actual pdf reading will happen, we mock it)
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_text("dummy")

    def mock_query(sql, params=(), commit=False):
        if "SELECT * FROM documents" in sql:
            return [{"id": "d1", "filename": "test.pdf", "mime_type": "application/pdf", "storage_path": str(pdf_path)}]
        return []

    fake = patch_query(monkeypatch, "app.services.document_ingest", mock_query)
    
    # Mock storage download
    def mock_download(key, fileobj):
        fileobj.write(b"dummy")
    monkeypatch.setattr("app.services.document_ingest.storage.download_fileobj", mock_download)
    
    # Mock PDF extraction
    monkeypatch.setattr("app.services.document_ingest.extract_text_from_pdf", lambda path: "This is a bill for $50 due 2026-08-01")

    # Mock LLM chat
    def mock_chat(provider, model, messages):
        return {
            "message": {
                "content": json.dumps({"items": [{"kind": "bill", "title": "Test Bill", "amount": 50, "due_date": "2026-08-01"}]})
            }
        }
    monkeypatch.setattr("app.services.document_ingest.chat", mock_chat)
    monkeypatch.setattr("app.services.document_ingest.current_user_id", lambda: "uid")

    res = document_ingest.analyze_document("d1")
    assert res["status"] == "analyzed"
    assert res["extracted_count"] == 1
    
    inserts = [c for c in fake.calls if "INSERT INTO document_extractions" in c[0]]
    assert len(inserts) == 1
    assert "bill" in inserts[0][1]


def test_approve_document_extraction(monkeypatch):
    from app.services import document_store
    from conftest import patch_query

    def q(sql, p=(), c=False):
        if "FROM document_extractions e" in sql:
            return [{"id": "e1", "document_id": "d1", "kind": "bill",
                     "payload": '{"title": "Test Bill", "amount": 50}', "filename": "test.pdf"}]
        if "SELECT id, amount FROM bills" in sql:
            return []  # no existing bill -> insert path
        if sql.strip().startswith("INSERT INTO bills"):
            return [{"id": "b1"}]
        return []
    fake = patch_query(monkeypatch, "app.services.document_store", q)

    r = document_store.approve_extraction("e1")
    assert r["status"] == "approved" and r["action"] == "created"
    assert len([c for c in fake.calls if "INSERT INTO bills" in c[0]]) == 1


def test_apply_item_dedups_recurring_subscription(monkeypatch):
    # A monthly statement re-lists the same sub: update the existing row (amount +
    # last_seen), never a duplicate insert.
    from app.services import document_store
    from conftest import patch_query

    def q(sql, p=(), c=False):
        if "SELECT id, amount FROM subscriptions" in sql:
            return [{"id": "s1", "amount": 9.99}]  # already tracked
        return []
    fake = patch_query(monkeypatch, "app.services.document_store", q)
    res = document_store.apply_item("subscription", {"title": "Netflix", "amount": 15.99},
                                    "statement.txt", uid="u1", seen_date="2026-07-04")
    assert res["action"] == "updated" and res["id"] == "s1"
    assert not any("INSERT INTO subscriptions" in c[0] for c in fake.calls)
    upd = next(c for c in fake.calls if "UPDATE subscriptions SET amount" in c[0])
    assert upd[1][0] == 15.99


def test_mark_ended_flips_active(monkeypatch):
    from app.services import document_store
    from conftest import patch_query
    fake = patch_query(monkeypatch, "app.services.document_store",
                       lambda sql, p=(), c=False: [{"id": "s1"}] if "UPDATE" in sql else [])
    out = document_store.mark_ended("subscription", "Spotify", uid="u1")
    assert out["ok"] is True
    upd = next(c for c in fake.calls if "UPDATE subscriptions SET active=false" in c[0])
    assert "AND active" in upd[0]
