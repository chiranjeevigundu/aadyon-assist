"""Aadyon Assist API — application factory and wiring."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.routers import agency, dashboard, email, system
from app.routers.crud import CRUD_ROUTERS


def create_app() -> FastAPI:
    app = FastAPI(title="Aadyon Assist", version="0.1.0")

    app.include_router(system.router)
    app.include_router(agency.router)
    app.include_router(email.router)
    for r in CRUD_ROUTERS:
        app.include_router(r)
    app.include_router(dashboard.router)

    dashboard_dir = get_settings().dashboard_dir
    if dashboard_dir.exists():
        app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

    return app


app = create_app()
