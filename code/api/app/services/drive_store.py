"""Persistence for drive files: dedup and save."""
from app.db.session import current_user_id, query


def already_synced(account_id: str, file_id: str) -> bool:
    """True if this file was already synced."""
    return bool(query(
        "SELECT 1 FROM drive_files WHERE account_id=%s AND file_id=%s",
        (account_id, str(file_id)),
    ))


def process_file(account_id: str, file: dict) -> tuple[int, int]:
    """Dedup and save one file. Returns (scanned_inc, found_inc)."""
    file_id = file.get("id")
    if not file_id:
        return (1, 0)
    
    name = file.get("name", "")
    mime = file.get("mimeType", "")
    link = file.get("webViewLink", "")
    size = int(file.get("size", 0)) if file.get("size") else None
    
    if already_synced(account_id, file_id):
        # Update metadata if it changed
        query(
            "UPDATE drive_files SET file_name=%s, mime_type=%s, web_view_link=%s, size_bytes=%s "
            "WHERE account_id=%s AND file_id=%s",
            (name, mime, link, size, account_id, str(file_id)),
            commit=True,
        )
        return (1, 0)
    
    query(
        "INSERT INTO drive_files (user_id, account_id, file_id, file_name, mime_type, web_view_link, size_bytes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (current_user_id(), account_id, str(file_id), name, mime, link, size),
        commit=True,
    )
    return (1, 1)
