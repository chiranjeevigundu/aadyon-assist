"""Auth: password hashing + JWT token round-trip (no DB needed)."""
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


def test_first_signup_is_allowed_without_an_invite(monkeypatch):
    """A fresh instance must be usable: minting an invite requires an account, so
    requiring one for the very first signup would lock everybody out."""
    from app.routers import auth as auth_router

    monkeypatch.setattr(auth_router.auth, "has_any_user", lambda: False)
    consumed = []
    monkeypatch.setattr(auth_router.auth, "consume_invite", lambda c: consumed.append(c))
    monkeypatch.setattr(
        auth_router.auth, "create_user", lambda e, p, d=None: {"id": "u1", "email": e}
    )
    monkeypatch.setattr(auth_router.auth, "make_token", lambda uid: "tok")
    monkeypatch.setattr(auth_router.auth, "get_user", lambda uid: {"id": "u1", "email": "a@b.c"})
    monkeypatch.setattr(auth_router, "_send_verification", lambda u: None)
    monkeypatch.setattr(auth_router, "_limit", lambda *a, **k: None)

    class S:
        invite_required = True

    monkeypatch.setattr(auth_router, "get_settings", lambda: S())
    out = auth_router.signup({"email": "a@b.c", "password": "pw"}, request=None)
    assert out["token"] == "tok"
    assert consumed == []  # no invite demanded for the first account


def test_later_signups_still_require_an_invite(monkeypatch):
    """Once an account exists, INVITE_REQUIRED is enforced again."""
    from app.routers import auth as auth_router

    monkeypatch.setattr(auth_router.auth, "has_any_user", lambda: True)

    def _reject(code):
        raise auth_router.auth.AuthError("an invite code is required")

    monkeypatch.setattr(auth_router.auth, "consume_invite", _reject)
    monkeypatch.setattr(auth_router, "_limit", lambda *a, **k: None)

    class S:
        invite_required = True

    monkeypatch.setattr(auth_router, "get_settings", lambda: S())
    import pytest as _pytest
    from fastapi import HTTPException

    with _pytest.raises(HTTPException) as e:
        auth_router.signup({"email": "b@c.d", "password": "pw"}, request=None)
    assert e.value.status_code == 400
    assert "invite code" in str(e.value.detail)
