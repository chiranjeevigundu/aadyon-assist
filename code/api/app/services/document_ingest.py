"""Document ingest entrypoint.

Extracts text/images from uploaded documents and uses the LLM to propose
deadlines, bills, or subscriptions.
"""
import base64
import json
from datetime import date

from pypdf import PdfReader

from app.db.session import current_user_id, query
from app.services import document_store, storage
from app.services.llm import chat

SYS_PROMPT = """You are a document analyzer. Extract actionable financial/life items from the document text or image.
Return a JSON object in this exact format, with NO markdown formatting around it:
{"items": [{"kind": "bill|deadline|subscription|info", "title": "short description", "amount": 10.50, "due_date": "YYYY-MM-DD", "summary": "One sentence summary", "confidence": 0.0}]}
`confidence` is your certainty (0.0-1.0) that this is a real, correctly-typed item — use >=0.8 only when the kind, title, and amount/date are unambiguous.
If nothing actionable is found, return {"items": []}.
"""

# Items at/above this confidence, with the fields their kind requires, are applied
# straight to the user's records (deduped); everything else waits in the review queue.
_AUTO_APPLY_MIN_CONFIDENCE = 0.8

def extract_text_from_pdf(fileobj) -> str:
    try:
        reader = PdfReader(fileobj)
        return "\n".join(page.extract_text() for page in reader.pages)
    except Exception as e:
        return f"[PDF parsing failed: {e}]"

def analyze_document(document_id: str) -> dict:
    rows = query("SELECT * FROM documents WHERE id = %s", (document_id,))
    if not rows:
        return {"error": "document not found"}
        
    doc = rows[0]
    object_key = doc["storage_path"]
    
    import io
    file_obj = io.BytesIO()
    try:
        storage.download_fileobj(object_key, file_obj)
        file_obj.seek(0)
    except Exception as e:
        return {"error": f"failed to download from S3: {e}"}

    messages = [{"role": "system", "content": SYS_PROMPT}]
    
    mime_type = doc.get("mime_type", "")
    if mime_type == "application/pdf":
        text = extract_text_from_pdf(file_obj)
        messages.append({"role": "user", "content": f"Document filename: {doc['filename']}\n\n{text}"})
    elif mime_type.startswith("image/"):
        b64 = base64.b64encode(file_obj.read()).decode("utf-8")
        messages.append({
            "role": "user", 
            "content": [
                {"type": "text", "text": f"Document filename: {doc['filename']}"},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
            ]
        })
    else:
        # Fallback to reading as text if possible, else error
        try:
            text = file_obj.read().decode("utf-8", errors="replace")
            messages.append({"role": "user", "content": f"Document filename: {doc['filename']}\n\n{text}"})
        except Exception:
            return {"error": f"unsupported mime type: {mime_type}"}

    try:
        # Use openrouter cheap for OCR/extraction
        resp = chat("openrouter", "openai/gpt-4o-mini", messages)
        content = resp["message"]["content"]
        # Strip markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        parsed = json.loads(content.strip())
        items = parsed.get("items", [])
    except Exception as e:
        query("UPDATE documents SET status='error' WHERE id=%s", (document_id,), commit=True)
        return {"error": f"LLM extraction failed: {e}"}

    uid = current_user_id()
    today = date.today()
    applied = 0
    for item in items:
        kind = item.get("kind", "info")
        # Auto-apply clear, high-confidence items straight to the user's records
        # (deduped); the rest stay pending for manual review.
        status = "pending"
        if kind in ("bill", "subscription", "deadline") and \
                float(item.get("confidence") or 0) >= _AUTO_APPLY_MIN_CONFIDENCE:
            res = document_store.apply_item(kind, item, doc["filename"], uid, seen_date=today)
            if not res.get("error"):
                status = "auto_applied"
                applied += 1
        query(
            "INSERT INTO document_extractions (user_id, document_id, kind, payload, summary, status) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, document_id, kind, json.dumps(item), item.get("summary", ""), status),
            commit=True,
        )

    query("UPDATE documents SET status='analyzed' WHERE id=%s", (document_id,), commit=True)
    return {"status": "analyzed", "extracted_count": len(items), "auto_applied": applied}
