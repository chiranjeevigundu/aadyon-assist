"""Serves the single-page dashboard's HTML entry point.

The asset URLs in the HTML are stamped with a build fingerprint (`?v=…`) when the
page is served. The dashboard ships as plain files with no bundler, so the script
names never change between releases — without the stamp a browser can keep running
last release's JS against this release's API. The stamp changes whenever any asset
changes, so an upgrade always lands as a whole.
"""
import hashlib
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.core.config import get_settings

router = APIRouter(tags=["dashboard"])


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    """The PWA manifest, served from the root.

    It declares `"scope": "/"`, and a manifest can only claim a scope at or below
    its own URL — served from /static/ the whole app would fall outside it. Root is
    also where iOS and Android look by convention.
    """
    return FileResponse(
        get_settings().dashboard_dir / "manifest.webmanifest",
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@lru_cache(maxsize=1)
def _asset_version(assets_dir: Path, stamp: float) -> str:
    """Short digest over every asset's name, size and mtime.

    `stamp` is the assets directory's own mtime: it is part of the cache key only so
    that adding or removing a file busts the memoised value. Contents are compared by
    (size, mtime) rather than by hashing bytes — the process restarts on deploy, so
    this only has to be right within one container's lifetime.
    """
    h = hashlib.sha256()
    for p in sorted(assets_dir.rglob("*")):
        if p.is_file():
            st = p.stat()
            h.update(f"{p.name}:{st.st_size}:{st.st_mtime_ns}".encode())
    return h.hexdigest()[:12]


def _page(filename: str) -> HTMLResponse:
    """Return a dashboard page with cache-busted asset URLs."""
    dashboard_dir = get_settings().dashboard_dir
    html = (dashboard_dir / filename).read_text(encoding="utf-8")
    assets = dashboard_dir / "assets"
    if assets.is_dir():
        html = _stamp(html, _asset_version(assets, assets.stat().st_mtime))
    # The page carries the asset fingerprints, so it must never be served from cache
    # itself — a stale page would keep pointing at the previous release's bundle.
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


def _stamp(html: str, version: str) -> str:
    """Append `?v=<version>` to every quoted /static/assets/<file> URL."""
    head, *rest = html.split('"/static/assets/')
    out = [head]
    for part in rest:
        end = part.find('"')
        out.append(f'"/static/assets/{part[:end]}?v={version}{part[end:]}')
    return "".join(out)


@router.get("/")
def home():
    """Net Worth — assets, liabilities, the running total, and the trend (front door)."""
    return _page("networth.html")


@router.get("/tracker")
def tracker():
    """The tracker: deadlines, debts, bills, subscriptions, shifts."""
    return _page("index.html")


@router.get("/data")
def data_admin():
    """Raw table console (developer surface) — only served when DEV_MODE=true.

    It exposes database table and column names directly, so it stays off in a normal
    deployment; the product UI covers everything a user needs."""
    if not get_settings().dev_mode:
        raise HTTPException(404, "Not Found")
    return _page("data.html")


@router.get("/assistant")
def assistant_page():
    """Personal Assistant (Aadyon Assist) chat interface."""
    return _page("assistant.html")


@router.get("/accounts")
def accounts_page():
    """Email accounts — register and (later) connect your mailboxes."""
    return _page("accounts.html")


@router.get("/login")
def login_page():
    """Login page for the web dashboard."""
    return _page("login.html")
