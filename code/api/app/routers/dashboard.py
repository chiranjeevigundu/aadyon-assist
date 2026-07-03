"""Serves the single-page dashboard's HTML entry point."""
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import get_settings

router = APIRouter(tags=["dashboard"])


@router.get("/")
def home():
    """Digital Me — identity + life dimensions (the new front door)."""
    return FileResponse(get_settings().dashboard_dir / "digital-me.html")


@router.get("/tracker")
def tracker():
    """The Phase 1 life-ops tracker (deadlines, debts, bills, subs, shifts)."""
    return FileResponse(get_settings().dashboard_dir / "index.html")


@router.get("/data")
def data_admin():
    """Generic data admin — view/add/edit/delete rows for every entity."""
    return FileResponse(get_settings().dashboard_dir / "data.html")


@router.get("/agency")
def agency_page():
    """The agentic org — CEO/teams/employees, task queue, approvals, model routing."""
    return FileResponse(get_settings().dashboard_dir / "agency.html")


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
