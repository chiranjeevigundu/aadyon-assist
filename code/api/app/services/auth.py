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
    """Return the user id (sub) or raise AuthError."""
    s = get_settings()
    if not s.jwt_secret:
        raise AuthError("JWT_SECRET is not set")
    try:
        data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_alg])
    except jwt.PyJWTError as e:
        raise AuthError(f"invalid token: {e}") from e
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

    rows = query_unscoped(
        "INSERT INTO users (email, password_hash, display_name) VALUES (%s,%s,%s) "
        "RETURNING id, email, display_name, created_at",
        (email, hash_password(password), display_name or email.split("@")[0]),
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
