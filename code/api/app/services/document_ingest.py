"""Document ingest entrypoint.

Extracts text/images from uploaded documents and uses the LLM to propose
deadlines, bills, or subscriptions.
"""
import base64
import json
from pathlib import Path
from pypdf import PdfReader

from app.db.session import current_user_id, query
from app.services.llm import chat

SYS_PROMPT = """You are a document analyzer. Extract actionable financial/life items from the document text or image.
Return a JSON object in this exact format, with NO markdown formatting around it:
{"items": [{"kind": "bill|deadline|subscription|info", "title": "short description", "amount": 10.50, "due_date": "YYYY-MM-DD", "summary": "One sentence summary"}]}
If nothing actionable is found, return {"items": []}.
"""

def extract_text_from_pdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() for page in reader.pages)
    except Exception as e:
        return f"[PDF parsing failed: {e}]"

def analyze_document(document_id: str) -> dict:
    rows = query("SELECT * FROM documents WHERE id = %s", (document_id,))
    if not rows:
        return {"error": "document not found"}
        
    doc = rows[0]
    file_path = Path(doc["storage_path"])
    if not file_path.exists():
        return {"error": "file not found on disk"}

    messages = [{"role": "system", "content": SYS_PROMPT}]
    
    mime_type = doc.get("mime_type", "")
    if mime_type == "application/pdf":
        text = extract_text_from_pdf(file_path)
        messages.append({"role": "user", "content": f"Document filename: {doc['filename']}\n\n{text}"})
    elif mime_type.startswith("image/"):
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
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
            text = file_path.read_text(errors="replace")
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
    for item in items:
        query(
            "INSERT INTO document_extractions (user_id, document_id, kind, payload, summary, status) "
            "VALUES (%s, %s, %s, %s, %s, 'pending')",
            (uid, document_id, item.get("kind", "info"), json.dumps(item), item.get("summary", "")),
            commit=True
        )

    query("UPDATE documents SET status='analyzed' WHERE id=%s", (document_id,), commit=True)
    return {"status": "analyzed", "extracted_count": len(items)}
