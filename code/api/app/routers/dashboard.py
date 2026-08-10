"""Serves the single-page dashboard's HTML entry point."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings

router = APIRouter(tags=["dashboard"])


@router.get("/")
def home():
    """Net Worth — assets, liabilities, the running total, and the trend (front door)."""
    return FileResponse(get_settings().dashboard_dir / "networth.html")


@router.get("/tracker")
def tracker():
    """The tracker: deadlines, debts, bills, subscriptions, shifts."""
    return FileResponse(get_settings().dashboard_dir / "index.html")


@router.get("/data")
def data_admin():
    """Raw table console (developer surface) — only served when DEV_MODE=true.

    It exposes database table and column names directly, so it stays off in a normal
    deployment; the product UI covers everything a user needs."""
    if not get_settings().dev_mode:
        raise HTTPException(404, "Not Found")
    return FileResponse(get_settings().dashboard_dir / "data.html")


@router.get("/assistant")
def assistant_page():
    """Personal Assistant (Aadyon Assist) chat interface."""
    return FileResponse(get_settings().dashboard_dir / "assistant.html")


@router.get("/accounts")
def accounts_page():
    """Email accounts — register and (later) connect your mailboxes."""
    return FileResponse(get_settings().dashboard_dir / "accounts.html")


@router.get("/login")
def login_page():
    """Login page for the web dashboard."""
    return FileResponse(get_settings().dashboard_dir / "login.html")
