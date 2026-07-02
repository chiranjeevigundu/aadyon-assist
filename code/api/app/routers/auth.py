"""Auth endpoints + the get_current_user dependency.

get_current_user is async on purpose: it is awaited in the request task, so the
`current_user` ContextVar it sets propagates into the (threadpool-run) sync
endpoints below it — where every query() then filters by RLS. A sync dependency
would set the var in a throwaway threadpool context that the endpoint never sees.
"""
from fastapi import APIRouter, Depends, Header, HTTPException

from app.db.session import set_current_user
from app.services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Resolve the request's user from the JWT and bind it for RLS. 401 if invalid."""
    token = _bearer(authorization)
    try:
        uid = auth.decode_token(token)
    except auth.AuthError as e:
        raise HTTPException(401, str(e)) from e
    user = auth.get_user(uid)
    if not user:
        raise HTTPException(401, "User not found or inactive")
    # Bind for downstream queries (propagates into the sync endpoint's context).
    set_current_user(uid)
    return user


def _public(user: dict) -> dict:
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "display_name": user.get("display_name"),
        "ntfy_topic": user.get("ntfy_topic"),
    }


@router.post("/signup")
def signup(payload: dict):
    try:
        user = auth.create_user(
            (payload or {}).get("email", ""),
            (payload or {}).get("password", ""),
            (payload or {}).get("display_name"),
        )
        token = auth.make_token(user["id"])
    # ValueError: psycopg2 rejects values Postgres can't store (e.g. NUL bytes
    # in email/display_name) — bad input, not a server error.
    except (auth.AuthError, ValueError) as e:
        raise HTTPException(400, str(e)) from e
    return {"token": token, "user": _public(user)}


@router.post("/login")
def login(payload: dict):
    email = (payload or {}).get("email", "")
    password = (payload or {}).get("password", "")
    user = auth.authenticate(email, password)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    try:
        token = auth.make_token(user["id"])
    except auth.AuthError as e:
        raise HTTPException(500, str(e)) from e
    return {"token": token, "user": _public(user)}


@router.patch("/me")
def update_me(payload: dict, user: dict = Depends(get_current_user)):
    """Update own account settings (display_name, ntfy_topic)."""
    allowed = {k: v for k, v in (payload or {}).items() if k in ("display_name", "ntfy_topic")}
    if not allowed:
        raise HTTPException(400, "Nothing to update. Allowed: display_name, ntfy_topic")
    sets = ", ".join(f"{k} = %s" for k in allowed)
    try:
        auth.query_unscoped(
            f"UPDATE users SET {sets} WHERE id = %s",
            tuple(allowed.values()) + (str(user["id"]),), commit=True,
        )
    # ValueError: psycopg2 rejects values Postgres can't store (e.g. NUL bytes).
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return _public(auth.get_user(user["id"]))


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return _public(user)
