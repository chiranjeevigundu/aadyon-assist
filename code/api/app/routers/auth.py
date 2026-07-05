"""Auth endpoints + the get_current_user dependency.

get_current_user is async on purpose: it is awaited in the request task, so the
`current_user` ContextVar it sets propagates into the (threadpool-run) sync
endpoints below it — where every query() then filters by RLS. A sync dependency
would set the var in a throwaway threadpool context that the endpoint never sees.

Family-and-friends hardening: signup is invite-gated, the auth endpoints are rate
limited, and email verification + password reset use short-lived purpose-scoped
tokens emailed via services.mailer.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.db.session import set_current_user
from app.services import auth, mailer, ratelimit

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _limit(request: Request, bucket: str, limit: int, window_seconds: int, extra: str = "") -> None:
    """429 if this IP (optionally + an extra key like the email) exceeds the window."""
    key = f"{bucket}:{_client_ip(request)}:{extra}"
    if not ratelimit.hit(key, limit, window_seconds):
        raise HTTPException(429, "Too many requests — please wait and try again.")


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
        "email_verified": user.get("email_verified", True),
    }


def _send_verification(user: dict) -> None:
    s = get_settings()
    token = auth.make_purpose_token(user["id"], "verify", s.email_token_minutes)
    link = f"{s.app_public_url}/api/auth/verify?token={token}"
    mailer.send_verification(user["email"], link)


@router.post("/signup")
def signup(payload: dict, request: Request):
    _limit(request, "signup", 5, 3600)
    s = get_settings()
    payload = payload or {}
    try:
        if s.invite_required:
            auth.consume_invite(payload.get("invite_code", ""))
        user = auth.create_user(
            payload.get("email", ""),
            payload.get("password", ""),
            payload.get("display_name"),
        )
        if s.invite_required:
            auth.mark_invite_used(payload.get("invite_code", ""), user["id"])
        token = auth.make_token(user["id"])
    # ValueError: psycopg2 rejects values Postgres can't store (e.g. NUL bytes).
    except (auth.AuthError, ValueError) as e:
        raise HTTPException(400, str(e)) from e
    _send_verification(user)
    return {"token": token, "user": _public(auth.get_user(user["id"]))}


@router.post("/login")
def login(payload: dict, request: Request):
    email = (payload or {}).get("email", "")
    password = (payload or {}).get("password", "")
    _limit(request, "login", 10, 300, extra=email.lower().strip())
    user = auth.authenticate(email, password)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    try:
        token = auth.make_token(user["id"])
    except auth.AuthError as e:
        raise HTTPException(500, str(e)) from e
    return {"token": token, "user": _public(user)}


@router.get("/verify", response_class=HTMLResponse)
def verify_email(token: str, request: Request):
    _limit(request, "verify", 20, 3600)
    try:
        uid = auth.decode_purpose_token(token, "verify")
    except auth.AuthError:
        return HTMLResponse("<h3>This verification link is invalid or has expired.</h3>", status_code=400)
    auth.mark_email_verified(uid)
    return HTMLResponse("<h3>Email verified — you're all set. You can close this tab.</h3>")


@router.post("/resend-verification")
def resend_verification(payload: dict, request: Request):
    _limit(request, "resend", 5, 3600)
    email = (payload or {}).get("email", "")
    user = auth.get_user_by_email(email)
    if user and not user.get("email_verified"):
        _send_verification(user)
    return {"status": "ok"}  # never reveal whether the account exists


@router.post("/forgot-password")
def forgot_password(payload: dict, request: Request):
    _limit(request, "forgot", 5, 3600)
    email = (payload or {}).get("email", "")
    user = auth.get_user_by_email(email)
    if user and user.get("is_active"):
        s = get_settings()
        token = auth.make_purpose_token(user["id"], "reset", s.email_token_minutes)
        link = f"{s.app_public_url}/api/auth/reset?token={token}"
        mailer.send_password_reset(user["email"], link)
    return {"status": "ok"}  # always 200 — no account enumeration


@router.get("/reset", response_class=HTMLResponse)
def reset_form(token: str):
    # Minimal web form for the emailed link; the mobile app can also POST /reset-password directly.
    return HTMLResponse(
        "<h3>Set a new password</h3>"
        '<form method="post" action="/api/auth/reset-password" '
        'onsubmit="event.preventDefault();fetch(this.action,{method:\'POST\','
        "headers:{'Content-Type':'application/json'},body:JSON.stringify("
        "{token:this.token.value,new_password:this.pw.value})})"
        ".then(r=>r.json()).then(d=>document.body.innerHTML=d.status==='ok'"
        "?'<h3>Password updated. You can log in now.</h3>':'<h3>Link invalid or expired.</h3>');\">"
        f'<input type="hidden" name="token" value="{token}">'
        '<input type="password" name="pw" placeholder="new password (min 8)" minlength="8" required>'
        '<button type="submit">Update password</button></form>'
    )


@router.post("/reset-password")
def reset_password(payload: dict, request: Request):
    _limit(request, "reset", 10, 3600)
    payload = payload or {}
    try:
        uid = auth.decode_purpose_token(payload.get("token", ""), "reset")
        auth.set_password(uid, payload.get("new_password", ""))
    except auth.AuthError as e:
        raise HTTPException(400, str(e)) from e
    return {"status": "ok"}


@router.post("/invites")
def create_invite(payload: dict, user: dict = Depends(get_current_user)):
    """Mint an invite code (any signed-in user, for a trusted instance)."""
    inv = auth.create_invite(note=(payload or {}).get("note"), created_by=user["id"])
    return inv


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
