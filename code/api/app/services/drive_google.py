"""Google Drive — device-code OAuth + files read.

Headless-friendly: the user authorizes by entering a short code at
google.com/device. We store only the refresh token (encrypted); access
tokens are minted per sync. Read-only (drive.readonly).
"""
import requests

from app.core.config import get_settings

GOOGLE_OAUTH = "https://oauth2.googleapis.com"
GOOGLE_DRIVE = "https://www.googleapis.com/drive/v3"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"


class GoogleError(RuntimeError):
    pass


def device_start() -> dict:
    s = get_settings()
    if not s.google_client_id:
        raise GoogleError("GOOGLE_CLIENT_ID is not set — register an OAuth app and add it to .env")
    r = requests.post(f"{GOOGLE_OAUTH}/device/code",
                      data={"client_id": s.google_client_id, "scope": SCOPE}, timeout=20)
    if not r.ok:
        raise GoogleError(f"devicecode {r.status_code}: {r.text[:300]}")
    return r.json()


def device_poll(device_code: str) -> dict:
    """One token attempt. Returns {ok, refresh_token} | {pending:True} | {error}."""
    s = get_settings()
    r = requests.post(f"{GOOGLE_OAUTH}/token", timeout=20, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": s.google_client_id, 
        "client_secret": s.google_client_secret,
        "device_code": device_code,
    })
    j = r.json() if r.content else {}
    if r.ok:
        return {"ok": True, "refresh_token": j.get("refresh_token")}
    if j.get("error") == "authorization_pending":
        return {"pending": True}
    return {"error": j.get("error_description") or j.get("error") or f"HTTP {r.status_code}"}


def refresh(refresh_token: str) -> dict:
    """Exchange a refresh token for a fresh access token."""
    s = get_settings()
    r = requests.post(f"{GOOGLE_OAUTH}/token", timeout=20, data={
        "grant_type": "refresh_token", 
        "client_id": s.google_client_id,
        "client_secret": s.google_client_secret,
        "refresh_token": refresh_token,
    })
    if not r.ok:
        raise GoogleError(f"refresh {r.status_code}: {r.text[:300]}")
    j = r.json()
    return {"access_token": j["access_token"], "refresh_token": j.get("refresh_token", refresh_token)}


def fetch_files(access_token: str, since_iso: str | None = None, page_size: int = 100) -> list:
    """Fetch recent files from Google Drive."""
    params = {
        "pageSize": str(page_size),
        "fields": "nextPageToken, files(id, name, mimeType, webViewLink, size, createdTime, modifiedTime)",
        "orderBy": "modifiedTime desc"
    }
    if since_iso:
        params["q"] = f"modifiedTime >= '{since_iso}'"

    r = requests.get(f"{GOOGLE_DRIVE}/files",
                     headers={"Authorization": f"Bearer {access_token}"},
                     params=params, timeout=30)
    if not r.ok:
        raise GoogleError(f"files {r.status_code}: {r.text[:300]}")
    return r.json().get("files", [])
