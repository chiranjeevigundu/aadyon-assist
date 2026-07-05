"""Auth: password hashing, JWT tokens, and user creation.

Multi-user support. Passwords are bcrypt-hashed (passlib); sessions are stateless
JWT bearer tokens signed with config.jwt_secret. `users` is not under RLS, so it is
read/written via query_unscoped; new users get their own agent org via seed_org().
"""
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.db.session import query, query_unscoped, set_current_user

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthError(RuntimeError):
    pass


# --------------------------------------------------------------------------- passwords
def hash_password(pw: str) -> str:
    return _pwd.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _pwd.verify(pw, hashed)
    except Exception:  # noqa: BLE001 — malformed/placeholder hash -> not a match
        return False


# --------------------------------------------------------------------------- tokens
def make_token(user_id) -> str:
    s = get_settings()
    if not s.jwt_secret:
        raise AuthError("JWT_SECRET is not set — add it to .env or secrets/jwt_secret.txt")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_alg)


def decode_token(token: str) -> str:
    """Return the user id (sub) for a normal session token, or raise AuthError.

    Rejects purpose-scoped tokens (verify/reset) so an email link can never be used
    as a session bearer token."""
    data = _decode(token)
    if data.get("purpose"):
        raise AuthError("not a session token")
    sub = data.get("sub")
    if not sub:
        raise AuthError("token missing subject")
    return sub


def _decode(token: str) -> dict:
    s = get_settings()
    if not s.jwt_secret:
        raise AuthError("JWT_SECRET is not set")
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_alg])
    except jwt.PyJWTError as e:
        raise AuthError(f"invalid token: {e}") from e


def make_purpose_token(user_id, purpose: str, minutes: int) -> str:
    """A short-lived, single-purpose token for an email link (verify/reset). The
    `purpose` claim prevents a verify link from acting as a reset link or a session."""
    s = get_settings()
    if not s.jwt_secret:
        raise AuthError("JWT_SECRET is not set")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "purpose": purpose,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_alg)


def decode_purpose_token(token: str, purpose: str) -> str:
    """Return the user id for a token of exactly this purpose, or raise AuthError."""
    data = _decode(token)
    if data.get("purpose") != purpose:
        raise AuthError("wrong or missing token purpose")
    sub = data.get("sub")
    if not sub:
        raise AuthError("token missing subject")
    return sub


# --------------------------------------------------------------------------- users
def get_user_by_email(email: str) -> dict | None:
    rows = query_unscoped("SELECT * FROM users WHERE email = %s", (email.lower().strip(),))
    return rows[0] if rows else None


def get_user(user_id) -> dict | None:
    rows = query_unscoped(
        "SELECT * FROM users WHERE id = %s AND is_active", (str(user_id),)
    )
    return rows[0] if rows else None


def create_user(email: str, password: str, display_name: str | None = None) -> dict:
    email = (email or "").lower().strip()
    if not email or "@" not in email:
        raise AuthError("a valid email is required")
    if not password or len(password) < 8:
        raise AuthError("password must be at least 8 characters")
    if get_user_by_email(email):
        raise AuthError("an account with that email already exists")

    budget = get_settings().default_monthly_token_budget or None  # 0 => unlimited (NULL)
    rows = query_unscoped(
        "INSERT INTO users (email, password_hash, display_name, monthly_token_budget, "
        "usage_period_start) VALUES (%s,%s,%s,%s, CURRENT_DATE) "
        "RETURNING id, email, display_name, created_at",
        (email, hash_password(password), display_name or email.split("@")[0], budget),
        commit=True,
    )
    user = rows[0]
    # Seed this user's own org (CEO + teams + leads). The scoped query sets the GUC
    # to the new user, so the RLS WITH CHECK on teams/agents inserts passes.
    set_current_user(user["id"])
    query("SELECT seed_org(%s)", (str(user["id"]),), commit=True)
    # Seed the user's initial Digital Me profile with their display name.
    d_name = display_name or email.split("@")[0]
    query("INSERT INTO profile (user_id, full_name) VALUES (%s, %s)", (str(user["id"]), d_name), commit=True)
    return user


def authenticate(email: str, password: str) -> dict | None:
    user = get_user_by_email(email)
    if not user or not user.get("is_active"):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def set_password(user_id, new_password: str) -> None:
    if not new_password or len(new_password) < 8:
        raise AuthError("password must be at least 8 characters")
    query_unscoped("UPDATE users SET password_hash = %s WHERE id = %s",
                   (hash_password(new_password), str(user_id)), commit=True)


def mark_email_verified(user_id) -> None:
    query_unscoped("UPDATE users SET email_verified = true WHERE id = %s",
                   (str(user_id),), commit=True)


# --------------------------------------------------------------------------- invites
def consume_invite(code: str) -> None:
    """Validate an unused, unexpired invite code and mark it pending-use. Raises
    AuthError if invalid. (Marked used_by after the account is actually created.)"""
    code = (code or "").strip()
    if not code:
        raise AuthError("an invite code is required")
    rows = query_unscoped(
        "SELECT id FROM invite_codes WHERE code = %s AND used_at IS NULL "
        "AND (expires_at IS NULL OR expires_at > now())",
        (code,),
    )
    if not rows:
        raise AuthError("invalid or already-used invite code")


def mark_invite_used(code: str, user_id) -> None:
    query_unscoped(
        "UPDATE invite_codes SET used_at = now(), used_by = %s WHERE code = %s AND used_at IS NULL",
        (str(user_id), (code or "").strip()), commit=True,
    )


def create_invite(note: str | None = None, created_by=None, expires_at=None) -> dict:
    """Mint a new invite code (admin/ops helper)."""
    import secrets as _secrets
    code = _secrets.token_urlsafe(9)
    rows = query_unscoped(
        "INSERT INTO invite_codes (code, note, created_by, expires_at) VALUES (%s,%s,%s,%s) "
        "RETURNING code, note, expires_at",
        (code, note, str(created_by) if created_by else None, expires_at), commit=True,
    )
    return rows[0]
