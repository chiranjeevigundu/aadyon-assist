"""Microsoft Graph (Outlook / Microsoft 365) — device-code OAuth + mail read.

Headless-friendly: the user authorizes by entering a short code at
microsoft.com/devicelogin. We store only the refresh token (encrypted); access
tokens are minted per sync. Read-only (Mail.Read).
"""
import requests

from app.core.config import get_settings

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "offline_access Mail.Read User.Read"


class GraphError(RuntimeError):
    pass


def _authority() -> str:
    return f"https://login.microsoftonline.com/{get_settings().ms_tenant}/oauth2/v2.0"


def device_start() -> dict:
    s = get_settings()
    if not s.ms_client_id:
        raise GraphError("MS_CLIENT_ID is not set — register an Azure app and add it to .env")
    r = requests.post(f"{_authority()}/devicecode",
                      data={"client_id": s.ms_client_id, "scope": SCOPE}, timeout=20)
    if not r.ok:
        raise GraphError(f"devicecode {r.status_code}: {r.text[:300]}")
    return r.json()  # device_code, user_code, verification_uri, interval, expires_in, message


def device_poll(device_code: str) -> dict:
    """One token attempt. Returns {ok, refresh_token} | {pending:True} | {error}."""
    s = get_settings()
    r = requests.post(f"{_authority()}/token", timeout=20, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": s.ms_client_id, "device_code": device_code,
    })
    j = r.json() if r.content else {}
    if r.ok:
        return {"ok": True, "refresh_token": j.get("refresh_token")}
    if j.get("error") in ("authorization_pending", "slow_down"):
        return {"pending": True}
    return {"error": j.get("error_description") or j.get("error") or f"HTTP {r.status_code}"}


def refresh(refresh_token: str) -> dict:
    """Exchange a refresh token for a fresh access token (MS may rotate the refresh token)."""
    s = get_settings()
    r = requests.post(f"{_authority()}/token", timeout=20, data={
        "grant_type": "refresh_token", "client_id": s.ms_client_id,
        "refresh_token": refresh_token, "scope": SCOPE,
    })
    if not r.ok:
        raise GraphError(f"refresh {r.status_code}: {r.text[:300]}")
    j = r.json()
    return {"access_token": j["access_token"], "refresh_token": j.get("refresh_token", refresh_token)}


def fetch_messages(access_token: str, since_iso: str | None = None, top: int = 40) -> list:
    params = {
        "$top": str(top),
        "$select": "id,subject,from,receivedDateTime,bodyPreview",
        "$orderby": "receivedDateTime desc",
    }
    if since_iso:
        params["$filter"] = f"receivedDateTime gt {since_iso}"
    r = requests.get(f"{GRAPH}/me/messages",
                     headers={"Authorization": f"Bearer {access_token}"},
                     params=params, timeout=30)
    if not r.ok:
        raise GraphError(f"messages {r.status_code}: {r.text[:300]}")
    return r.json().get("value", [])
