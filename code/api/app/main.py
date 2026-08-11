"""Aadyon Assist API — application factory and wiring."""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.routers import assistant, auth, dashboard, email, system, bank, documents, networth
from app.routers.auth import get_current_user
from app.routers.crud import CRUD_ROUTERS


class RevalidatingStatic(StaticFiles):
    """StaticFiles that asks the browser to revalidate instead of guessing.

    Without an explicit Cache-Control, browsers apply heuristic caching and can
    serve a stale dashboard bundle for a long time after an upgrade — the JS has
    no content hash in its filename, so the URL never changes. `no-cache` still
    allows a conditional request, so the ETag makes the common case a cheap 304.
    """

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


def _bootstrap_storage() -> None:
    """On an S3-mode deployment, create the bucket if it doesn't exist so a fresh AWS
    account or a just-started emulator works with zero manual `aws s3 mb`. Best-effort:
    never blocks or fails startup — if the store is down or auto-create is off, we log
    and carry on; the first upload will surface any real problem."""
    s = get_settings()
    if s.storage_backend != "s3" or not s.s3_auto_create_bucket:
        return
    log = logging.getLogger(__name__)
    try:
        from app.services import storage

        if storage.ensure_bucket():
            log.info("Storage ready: bucket %r via %s", s.s3_bucket, s.s3_endpoint_url or "AWS S3")
    except Exception as e:  # noqa: BLE001 — startup must never crash on storage
        log.warning("Storage bootstrap skipped: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap_storage()
    yield


def create_app() -> FastAPI:
    # Swagger/ReDoc/OpenAPI are developer surfaces: exposed only when DEV_MODE=true.
    _dev = get_settings().dev_mode
    app = FastAPI(
        title="Aadyon Assist",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs" if _dev else None,
        redoc_url="/redoc" if _dev else None,
        openapi_url="/openapi.json" if _dev else None,
    )

    # Postgres text can never contain NUL (0x00); psycopg2 raises a bare ValueError
    # when such a value reaches a query, which would surface as a 500. Reject NUL in
    # query strings up front so every filter param (e.g. ?status=) fails as 422 —
    # one guard for all current and future routers instead of per-endpoint checks.
    @app.middleware("http")
    async def reject_nul_in_query(request: Request, call_next):
        q = request.url.query
        if "%00" in q or "\x00" in q:
            return JSONResponse({"detail": "NUL bytes are not allowed"}, status_code=422)
        return await call_next(request)

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
    app.include_router(email.router, dependencies=guard)
    app.include_router(bank.router, dependencies=guard)
    app.include_router(networth.router, dependencies=guard)
    app.include_router(documents.router, dependencies=guard)
    app.include_router(assistant.router, dependencies=guard)
    for r in CRUD_ROUTERS:
        app.include_router(r, dependencies=guard)

    dashboard_dir = get_settings().dashboard_dir
    if dashboard_dir.exists():
        app.mount("/static", RevalidatingStatic(directory=str(dashboard_dir)), name="static")

    return app


app = create_app()
