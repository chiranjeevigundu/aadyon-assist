"""Google OAuth code exchange + Gmail fetch (network mocked)."""
import pytest

from app.services import google_oauth
from app.services.google_oauth import GoogleOAuthError


class _Resp:
    def __init__(self, ok=True, payload=None, status=200, text=""):
        self.ok = ok
        self._payload = payload or {}
        self.status_code = status
        self.text = text
        self.content = b"x"

    def json(self):
        return self._payload


def test_client_config_requires_client_id(monkeypatch):
    monkeypatch.setattr(google_oauth.get_settings(), "google_client_id", "", raising=False)
    with pytest.raises(GoogleOAuthError):
        google_oauth.client_config()


def test_client_config_returns_id(monkeypatch):
    monkeypatch.setattr(google_oauth.get_settings(), "google_client_id", "abc", raising=False)
    cfg = google_oauth.client_config()
    assert cfg["client_id"] == "abc" and cfg["auth_endpoint"] and cfg["scope"]


def test_exchange_code_success(monkeypatch):
    monkeypatch.setattr(google_oauth.get_settings(), "google_client_id", "abc", raising=False)
    monkeypatch.setattr(google_oauth.requests, "post",
                        lambda *a, **k: _Resp(payload={"refresh_token": "rt", "access_token": "at"}))
    tok = google_oauth.exchange_code("code", "verifier", "scheme:/oauthredirect")
    assert tok["refresh_token"] == "rt"


def test_exchange_code_error_uses_description(monkeypatch):
    monkeypatch.setattr(google_oauth.get_settings(), "google_client_id", "abc", raising=False)
    monkeypatch.setattr(google_oauth.requests, "post",
                        lambda *a, **k: _Resp(ok=False, payload={"error": "invalid_grant",
                                                                 "error_description": "bad code"}))
    with pytest.raises(GoogleOAuthError, match="bad code"):
        google_oauth.exchange_code("code", "verifier", "scheme:/oauthredirect")


def test_exchange_code_without_refresh_token(monkeypatch):
    monkeypatch.setattr(google_oauth.get_settings(), "google_client_id", "abc", raising=False)
    monkeypatch.setattr(google_oauth.requests, "post",
                        lambda *a, **k: _Resp(payload={"access_token": "at"}))
    with pytest.raises(GoogleOAuthError, match="no refresh token"):
        google_oauth.exchange_code("code", "verifier", "scheme:/oauthredirect")


def test_refresh_success(monkeypatch):
    monkeypatch.setattr(google_oauth.get_settings(), "google_client_id", "abc", raising=False)
    monkeypatch.setattr(google_oauth.requests, "post",
                        lambda *a, **k: _Resp(payload={"access_token": "at"}))
    tok = google_oauth.refresh("rt")
    assert tok == {"access_token": "at", "refresh_token": "rt"}  # Google does not rotate


def test_normalize_message():
    m = google_oauth.normalize_message({
        "id": "m1", "internalDate": "1783648904000", "snippet": "Your bill is due",
        "payload": {"headers": [{"name": "From", "value": "Netflix <billing@netflix.com>"},
                                {"name": "Subject", "value": "Your bill"}]},
    })
    assert m["id"] == "m1"
    assert m["from"] == "Netflix <billing@netflix.com>"
    assert m["subject"] == "Your bill"
    assert m["snippet"] == "Your bill is due"
    assert m["date"] == "2026-07-10T02:01:44Z"


def test_normalize_message_empty():
    m = google_oauth.normalize_message({})
    assert m == {"id": None, "from": "", "subject": "", "date": None, "snippet": ""}


def test_fetch_messages(monkeypatch):
    monkeypatch.setattr(google_oauth.get_settings(), "google_client_id", "abc", raising=False)

    def fake_get(url, **k):
        if url.endswith("/users/me/messages"):
            return _Resp(payload={"messages": [{"id": "m1"}]})
        return _Resp(payload={"id": "m1", "snippet": "hi", "payload": {"headers": []}})

    monkeypatch.setattr(google_oauth.requests, "get", fake_get)
    msgs = google_oauth.fetch_messages("token", newer_than_days=14)
    assert msgs == [{"id": "m1", "from": "", "subject": "", "date": None, "snippet": "hi"}]


def test_fetch_messages_http_error(monkeypatch):
    monkeypatch.setattr(google_oauth.requests, "get",
                        lambda *a, **k: _Resp(ok=False, status=403, text="forbidden"))
    with pytest.raises(GoogleOAuthError):
        google_oauth.fetch_messages("token", newer_than_days=14)


def test_ingest_dispatches_oauth_google(monkeypatch):
    from app.services import email_ingest
    monkeypatch.setattr(email_ingest, "query",
                        lambda *a, **k: [{"id": "a1", "auth_type": "oauth_google", "secret_enc": "x"}])
    monkeypatch.setattr(email_ingest, "sync_gmail", lambda account_id, acct, s: {"routed": "gmail"})
    assert email_ingest.sync_account("a1") == {"routed": "gmail"}
