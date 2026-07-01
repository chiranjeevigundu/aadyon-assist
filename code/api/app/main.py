"""Aadyon Assist API — application factory and wiring."""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.routers import agency, assistant, auth, dashboard, email, system
from app.routers.auth import get_current_user
from app.routers.crud import CRUD_ROUTERS


def create_app() -> FastAPI:
    app = FastAPI(title="Aadyon Assist", version="0.2.0")

    # CORS — the native mobile app makes cross-origin requests. Wide-open origins
    # are acceptable because data endpoints now require a JWT bearer token (the app
    # is multi-user); Tailscale remains defense-in-depth. See AGENTS.md security.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Public: auth (login/signup), health, and the dashboard HTML shells + static.
    app.include_router(auth.router)
    app.include_router(system.router)  # /api/health is public; data routes self-guard
    app.include_router(dashboard.router)

    # Protected: every per-user data + action router requires a valid user, which
    # also binds the RLS context for all its queries.
    guard = [Depends(get_current_user)]
    app.include_router(agency.router, dependencies=guard)
    app.include_router(email.router, dependencies=guard)
    app.include_router(assistant.router, dependencies=guard)
    for r in CRUD_ROUTERS:
        app.include_router(r, dependencies=guard)

    dashboard_dir = get_settings().dashboard_dir
    if dashboard_dir.exists():
        app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

    return app


app = create_app()
