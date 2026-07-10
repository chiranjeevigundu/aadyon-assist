"""Google OAuth (authorization-code + PKCE) + Gmail REST mail fetch.

Gmail scopes are not allowed in Google's limited-input device flow, so unlike
Microsoft the sign-in happens ON the phone: the app runs the PKCE authorization
request against accounts.google.com (iOS-type OAuth client, reversed-client-id
redirect scheme) and posts the one-time code here. We exchange it server-side
and store only the refresh token (encrypted); access tokens are minted per
sync. Read-only (gmail.readonly).
"""
from datetime import datetime, timezone

import requests

from app.core.config import get_settings

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GMAIL = "https://gmail.googleapis.com/gmail/v1"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GoogleOAuthError(RuntimeError):
    pass


def _client_id() -> str:
    cid = get_settings().google_client_id
    if not cid:
        raise GoogleOAuthError(
            "GOOGLE_CLIENT_ID is not set — create an iOS OAuth client "
            "(console.cloud.google.com → Credentials) and add it to .env"
        )
    return cid


def client_config() -> dict:
    """What the mobile app needs to run the PKCE auth request itself."""
    return {"client_id": _client_id(), "auth_endpoint": AUTH_ENDPOINT, "scope": SCOPE}


def _token_post(data: dict):
    """POST to the token endpoint; network failures become GoogleOAuthError (never a 500)."""
    try:
        return requests.post(TOKEN_ENDPOINT, data=data, timeout=20)
    except requests.RequestException as e:
        raise GoogleOAuthError(f"can't reach Google: {e}") from e


def exchange_code(code: str, code_verifier: str, redirect_uri: str) -> dict:
    """Swap the app's one-time auth code for tokens (PKCE; iOS clients have no secret)."""
    s = get_settings()
    data = {
        "grant_type": "authorization_code", "client_id": _client_id(),
        "code": code, "code_verifier": code_verifier, "redirect_uri": redirect_uri,
    }
    if s.google_client_secret:  # web-type clients also send the secret
        data["client_secret"] = s.google_client_secret
    r = _token_post(data)
    j = r.json() if r.content else {}
    if not r.ok:
        raise GoogleOAuthError(j.get("error_description") or j.get("error") or f"token {r.status_code}")
    if not j.get("refresh_token"):
        # Google only reissues a refresh token on a fresh grant.
        raise GoogleOAuthError(
            "Google returned no refresh token — remove this app at "
            "myaccount.google.com/permissions and connect again"
        )
    return {"refresh_token": j["refresh_token"], "access_token": j.get("access_token")}


def refresh(refresh_token: str) -> dict:
    """Mint an access token (Google does not rotate refresh tokens)."""
    s = get_settings()
    data = {"grant_type": "refresh_token", "client_id": _client_id(), "refresh_token": refresh_token}
    if s.google_client_secret:
        data["client_secret"] = s.google_client_secret
    r = _token_post(data)
    if not r.ok:
        raise GoogleOAuthError(f"refresh {r.status_code}: {r.text[:300]}")
    return {"access_token": r.json()["access_token"], "refresh_token": refresh_token}


def normalize_message(j: dict) -> dict:
    """Gmail message JSON -> {id, from, subject, date, snippet} (pure; unit-tested)."""
    headers = {h.get("name", "").lower(): h.get("value", "")
               for h in ((j.get("payload") or {}).get("headers") or [])}
    ts = j.get("internalDate")
    date = (datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if ts else None)
    return {"id": j.get("id"), "from": headers.get("from", ""),
            "subject": headers.get("subject", ""), "date": date, "snippet": j.get("snippet", "")}


def fetch_messages(access_token: str, newer_than_days: int, top: int = 40) -> list:
    """List recent inbox mail and normalize each message (metadata + snippet only)."""
    h = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(f"{GMAIL}/users/me/messages", headers=h, timeout=30,
                     params={"q": f"newer_than:{newer_than_days}d", "maxResults": str(top)})
    if not r.ok:
        raise GoogleOAuthError(f"messages {r.status_code}: {r.text[:300]}")
    out = []
    for m in r.json().get("messages") or []:
        rm = requests.get(f"{GMAIL}/users/me/messages/{m['id']}", headers=h, timeout=30,
                          params={"format": "metadata",
                                  "metadataHeaders": ["From", "Subject"]})
        if not rm.ok:  # skip a bad message, keep going
            continue
        out.append(normalize_message(rm.json()))
    return out
