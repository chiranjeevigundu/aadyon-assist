"""Symmetric encryption for stored secrets (email app-passwords).

Uses Fernet (AES-128-CBC + HMAC) with a key from config (secret file or env).
The key lives outside the database, so the encrypted column is useless on its own.
"""
from cryptography.fernet import Fernet

from app.core.config import get_settings


class CryptoError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = get_settings().email_enc_key
    if not key:
        raise CryptoError(
            "EMAIL_ENC_KEY is not set. Generate one with "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode())
    except Exception as e:  # noqa: BLE001
        raise CryptoError(f"Invalid EMAIL_ENC_KEY: {e}") from e


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
