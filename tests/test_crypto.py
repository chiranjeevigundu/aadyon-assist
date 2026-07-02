"""Fernet encryption of stored email secrets: round-trip + missing-key error."""
import pytest
from cryptography.fernet import Fernet

from app.services import crypto


def test_round_trip(monkeypatch):
    monkeypatch.setenv("EMAIL_ENC_KEY", Fernet.generate_key().decode())
    token = crypto.encrypt("hunter2-app-password")
    assert token != "hunter2-app-password"          # actually encrypted
    assert crypto.decrypt(token) == "hunter2-app-password"


def test_ciphertext_is_not_deterministic(monkeypatch):
    monkeypatch.setenv("EMAIL_ENC_KEY", Fernet.generate_key().decode())
    assert crypto.encrypt("x") != crypto.encrypt("x")  # Fernet uses a random IV


def test_missing_key_raises(monkeypatch):
    monkeypatch.setenv("EMAIL_ENC_KEY", "")
    # No /run/secrets/email_key in the test env, so the key is genuinely absent.
    with pytest.raises(crypto.CryptoError):
        crypto.encrypt("x")


def test_invalid_key_raises(monkeypatch):
    monkeypatch.setenv("EMAIL_ENC_KEY", "not-a-valid-fernet-key")
    with pytest.raises(crypto.CryptoError):
        crypto.encrypt("x")
