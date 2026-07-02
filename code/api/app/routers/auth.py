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
    except auth.AuthError as e:
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


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return _public(user)
