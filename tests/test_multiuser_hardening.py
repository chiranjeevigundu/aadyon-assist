"""Family-and-friends hardening: purpose tokens, invites, rate limiting, cost caps."""
import pytest

from app.services import auth, ratelimit, usage
from conftest import patch_query


# --------------------------------------------------------------------------- purpose tokens
def test_purpose_token_roundtrip_and_isolation(monkeypatch):
    monkeypatch.setattr(auth, "get_settings",
                        lambda: type("S", (), {"jwt_secret": "s", "jwt_alg": "HS256"})())
    tok = auth.make_purpose_token("u1", "reset", 60)
    assert auth.decode_purpose_token(tok, "reset") == "u1"
    # A reset token must not validate as a verify token...
    with pytest.raises(auth.AuthError):
        auth.decode_purpose_token(tok, "verify")
    # ...nor as a normal session token.
    with pytest.raises(auth.AuthError):
        auth.decode_token(tok)


def test_session_token_is_not_a_purpose_token(monkeypatch):
    monkeypatch.setattr(auth, "get_settings",
                        lambda: type("S", (), {"jwt_secret": "s", "jwt_alg": "HS256",
                                               "jwt_expire_minutes": 60})())
    tok = auth.make_token("u9")
    assert auth.decode_token(tok) == "u9"
    with pytest.raises(auth.AuthError):
        auth.decode_purpose_token(tok, "reset")


# --------------------------------------------------------------------------- invites
def test_consume_invite_rejects_missing_and_unknown(monkeypatch):
    with pytest.raises(auth.AuthError):
        auth.consume_invite("")
    patch_query(monkeypatch, "app.services.auth", lambda sql, p=(), c=False: [])  # no match
    with pytest.raises(auth.AuthError):
        auth.consume_invite("nope")


def test_consume_invite_accepts_valid(monkeypatch):
    patch_query(monkeypatch, "app.services.auth", lambda sql, p=(), c=False: [{"id": "i1"}])
    auth.consume_invite("goodcode")  # does not raise


# --------------------------------------------------------------------------- rate limiter
def test_rate_limiter_blocks_after_limit():
    ratelimit.reset()
    assert all(ratelimit.hit("k", 3, 60) for _ in range(3))  # first 3 allowed
    assert ratelimit.hit("k", 3, 60) is False                 # 4th blocked
    assert ratelimit.hit("other", 3, 60) is True              # separate key unaffected


# --------------------------------------------------------------------------- cost caps
def test_usage_unlimited_when_budget_null(monkeypatch):
    patch_query(monkeypatch, "app.services.usage",
                lambda sql, p=(), c=False: [{"budget": None, "used": 0}] if "SELECT" in sql else [])
    out = usage.check("u1")
    assert out["allowed"] is True and out["unlimited"] is True


def test_usage_blocks_when_over_budget(monkeypatch):
    patch_query(monkeypatch, "app.services.usage",
                lambda sql, p=(), c=False: [{"budget": 100, "used": 100}] if "SELECT" in sql else [])
    out = usage.check("u1")
    assert out["allowed"] is False and out["remaining"] == 0


def test_usage_allows_under_budget(monkeypatch):
    patch_query(monkeypatch, "app.services.usage",
                lambda sql, p=(), c=False: [{"budget": 100, "used": 40}] if "SELECT" in sql else [])
    out = usage.check("u1")
    assert out["allowed"] is True and out["remaining"] == 60


def test_usage_record_noop_on_zero(monkeypatch):
    fake = patch_query(monkeypatch, "app.services.usage", lambda sql, p=(), c=False: [])
    usage.record("u1", 0)
    assert not fake.calls  # nothing written
