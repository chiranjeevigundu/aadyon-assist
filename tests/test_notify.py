"""Self-hosted ntfy push: no-op when unset, POSTs when configured, never raises."""
from app.services import notify


class _Resp:
    def raise_for_status(self):  # pretend success
        return None


def test_no_topic_is_noop(monkeypatch):
    monkeypatch.setattr(notify.get_settings(), "ntfy_topic", "", raising=False)
    assert notify.push_briefing("hello") is False


def test_pushes_when_topic_set(monkeypatch):
    s = notify.get_settings()
    monkeypatch.setattr(s, "ntfy_topic", "secret-topic", raising=False)
    monkeypatch.setattr(s, "ntfy_internal_url", "http://ntfy", raising=False)
    sent = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        sent["url"] = url
        sent["data"] = data
        return _Resp()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    assert notify.push_briefing("# Briefing") is True
    assert sent["url"] == "http://ntfy/secret-topic"
    assert sent["data"] == b"# Briefing"


def test_push_failure_is_swallowed(monkeypatch):
    s = notify.get_settings()
    monkeypatch.setattr(s, "ntfy_topic", "t", raising=False)
    monkeypatch.setattr(s, "ntfy_internal_url", "http://ntfy", raising=False)

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(notify.requests, "post", boom)
    # A failed push must never break the briefing.
    assert notify.push_briefing("x") is False
