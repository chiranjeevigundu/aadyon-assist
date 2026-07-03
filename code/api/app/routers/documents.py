"""Document endpoints: upload and review queue."""
from uuid import UUID
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks

from app.db.session import current_user_id, query
from app.services import document_ingest, document_store, storage

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a file and kick off async analysis."""
    uid = current_user_id()
    
    # S3 Object Key: uid/filename
    safe_name = "".join(c for c in (file.filename or "unnamed") if c.isalnum() or c in "._- ")
    if not safe_name:
        safe_name = "unnamed"
    object_key = f"{uid}/{safe_name}"
    
    # We read the file to get size, then wrap in BytesIO for boto3 since FastAPI UploadFile 
    # doesn't natively expose a good interface for boto3 upload_fileobj sometimes.
    content = await file.read()
    size = len(content)
    
    import io
    storage.upload_fileobj(io.BytesIO(content), object_key, file.content_type)
    
    # DB insert
    rows = query(
        "INSERT INTO documents (user_id, filename, mime_type, storage_path, size_bytes) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (uid, safe_name, file.content_type, object_key, size),
        commit=True
    )
    doc_id = str(rows[0]["id"])
    
    # Queue analysis
    background_tasks.add_task(document_ingest.analyze_document, doc_id)
    
    return {"status": "uploaded", "document_id": doc_id}


@router.get("/extractions")
def get_extractions(status: str = "pending"):
    return query(
        "SELECT e.*, d.filename FROM document_extractions e "
        "JOIN documents d ON d.id = e.document_id "
        "WHERE e.status = %s ORDER BY e.created_at DESC",
        (status,)
    )


@router.post("/extractions/{ext_id}/approve")
def approve_extraction(ext_id: UUID):
    r = document_store.approve_extraction(str(ext_id))
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return r


@router.post("/extractions/{ext_id}/dismiss")
def dismiss_extraction(ext_id: UUID):
    query("UPDATE document_extractions SET status='dismissed' WHERE id=%s", (str(ext_id),), commit=True)
    return {"status": "dismissed"}
