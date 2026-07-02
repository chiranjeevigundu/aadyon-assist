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

    fake = patch_query(monkeypatch, "app.services.document_store", lambda sql, p=(), c=False: [
        {"id": "e1", "document_id": "d1", "kind": "bill", "payload": '{"title": "Test Bill", "amount": 50}', "filename": "test.pdf"}
    ])
    
    r = document_store.approve_extraction("e1")
    assert r["status"] == "approved"
    
    inserts = [c for c in fake.calls if "INSERT INTO bills" in c[0]]
    assert len(inserts) == 1
