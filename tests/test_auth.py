"""Auth: password hashing + JWT token round-trip (no DB needed)."""
import time

import pytest

from app.core.config import get_settings
from app.services import auth


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    # jwt_secret is a property that reads the JWT_SECRET env var (no secret file in tests).
    monkeypatch.setenv("JWT_SECRET", "test-secret-abc")
    yield


def test_password_hash_roundtrip():
    h = auth.hash_password("correct horse battery")
    assert h != "correct horse battery"
    assert auth.verify_password("correct horse battery", h) is True
    assert auth.verify_password("wrong", h) is False


def test_verify_bad_hash_is_false():
    # A placeholder/garbage hash must not raise, just fail to match.
    assert auth.verify_password("anything", "x-not-set") is False


def test_token_roundtrip():
    tok = auth.make_token("user-123")
    assert auth.decode_token(tok) == "user-123"


def test_expired_token_rejected(monkeypatch):
    # Mint a token that is already expired (jwt_expire_minutes is a plain attribute).
    monkeypatch.setattr(get_settings(), "jwt_expire_minutes", -1)
    tok = auth.make_token("user-9")
    with pytest.raises(auth.AuthError):
        auth.decode_token(tok)


def test_tampered_token_rejected():
    tok = auth.make_token("user-1")
    with pytest.raises(auth.AuthError):
        auth.decode_token(tok + "tamper")


def test_no_secret_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "")
    with pytest.raises(auth.AuthError):
        auth.make_token("u")
