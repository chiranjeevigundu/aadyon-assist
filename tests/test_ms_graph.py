"""Microsoft Graph device-code OAuth + mail fetch (network mocked)."""
import pytest

from app.services import ms_graph
from app.services.ms_graph import GraphError


class _Resp:
    def __init__(self, ok=True, payload=None, status=200, text=""):
        self.ok = ok
        self._payload = payload or {}
        self.status_code = status
        self.text = text
        self.content = b"x"

    def json(self):
        return self._payload


def test_device_start_requires_client_id(monkeypatch):
    monkeypatch.setattr(ms_graph.get_settings(), "ms_client_id", "", raising=False)
    with pytest.raises(GraphError):
        ms_graph.device_start()


def test_device_start_returns_code(monkeypatch):
    monkeypatch.setattr(ms_graph.get_settings(), "ms_client_id", "abc", raising=False)
    monkeypatch.setattr(ms_graph.requests, "post",
                        lambda *a, **k: _Resp(payload={"user_code": "ABCD-EFGH",
                                                       "device_code": "dev"}))
    d = ms_graph.device_start()
    assert d["user_code"] == "ABCD-EFGH"


def test_device_poll_pending(monkeypatch):
    monkeypatch.setattr(ms_graph.requests, "post",
                        lambda *a, **k: _Resp(ok=False, payload={"error": "authorization_pending"}))
    assert ms_graph.device_poll("dev") == {"pending": True}


def test_device_poll_success(monkeypatch):
    monkeypatch.setattr(ms_graph.requests, "post",
                        lambda *a, **k: _Resp(ok=True, payload={"refresh_token": "rt"}))
    res = ms_graph.device_poll("dev")
    assert res["ok"] is True and res["refresh_token"] == "rt"


def test_device_poll_error(monkeypatch):
    monkeypatch.setattr(ms_graph.requests, "post",
                        lambda *a, **k: _Resp(ok=False, payload={"error": "expired_token",
                                                                 "error_description": "gone"}))
    assert ms_graph.device_poll("dev")["error"] == "gone"


def test_fetch_messages(monkeypatch):
    monkeypatch.setattr(ms_graph.requests, "get",
                        lambda *a, **k: _Resp(payload={"value": [{"id": "1", "subject": "Hi"}]}))
    msgs = ms_graph.fetch_messages("token", since_iso="2026-01-01T00:00:00Z")
    assert msgs == [{"id": "1", "subject": "Hi"}]


def test_fetch_messages_http_error(monkeypatch):
    monkeypatch.setattr(ms_graph.requests, "get",
                        lambda *a, **k: _Resp(ok=False, status=403, text="forbidden"))
    with pytest.raises(GraphError):
        ms_graph.fetch_messages("token")
