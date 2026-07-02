"""Uploads local PostgreSQL backup dumps to S3."""
import os
from pathlib import Path
from app.services import storage

BACKUP_DIR = Path("/srv/backups")

def sync_backups():
    """Scans the mounted /srv/backups for new .sql.gz dumps and uploads them to S3."""
    if not BACKUP_DIR.exists():
        print("[backup_sync] /srv/backups not mounted, skipping.", flush=True)
        return

    # Check already uploaded
    synced_marker = BACKUP_DIR / ".synced"
    synced_files = set()
    if synced_marker.exists():
        synced_files = set(synced_marker.read_text().splitlines())

    new_syncs = []
    
    # Check for daily files like: /srv/backups/daily/db-20260702-000000.sql.gz
    for root, _, files in os.walk(BACKUP_DIR):
        for file in files:
            if file.endswith(".sql.gz"):
                rel_path = str(Path(root).relative_to(BACKUP_DIR) / file)
                if rel_path not in synced_files:
                    file_path = str(Path(root) / file)
                    object_key = f"backups/{file}"
                    try:
                        print(f"[backup_sync] Uploading {rel_path} to {object_key}...", flush=True)
                        storage.upload_file(file_path, object_key)
                        synced_files.add(rel_path)
                        new_syncs.append(rel_path)
                    except Exception as e:
                        print(f"[backup_sync] Error uploading {rel_path}: {e}", flush=True)

    if new_syncs:
        synced_marker.write_text("\n".join(synced_files))
        print(f"[backup_sync] Synced {len(new_syncs)} new backup(s).", flush=True)
    else:
        print("[backup_sync] No new backups to sync.", flush=True)

if __name__ == "__main__":
    sync_backups()
