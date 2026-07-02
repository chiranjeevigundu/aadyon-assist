"""Google Calendar — device-code OAuth + events read.

Headless-friendly: the user authorizes by entering a short code at
google.com/device. We store only the refresh token (encrypted); access
tokens are minted per sync. Read-only (calendar.readonly).
"""
import requests
from datetime import datetime, timezone

from app.core.config import get_settings

GOOGLE_OAUTH = "https://oauth2.googleapis.com"
GOOGLE_CAL = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


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
    return r.json()  # device_code, user_code, verification_url, interval, expires_in


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


def fetch_events(access_token: str, since_iso: str | None = None, max_results: int = 40) -> list:
    """Fetch upcoming calendar events. If since_iso is not provided, defaults to now."""
    if not since_iso:
        since_iso = datetime.now(timezone.utc).isoformat()
    
    # We want single events (expanding recurring events) ordered by start time
    params = {
        "maxResults": str(max_results),
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": since_iso
    }
    r = requests.get(f"{GOOGLE_CAL}/calendars/primary/events",
                     headers={"Authorization": f"Bearer {access_token}"},
                     params=params, timeout=30)
    if not r.ok:
        raise GoogleError(f"events {r.status_code}: {r.text[:300]}")
    return r.json().get("items", [])
