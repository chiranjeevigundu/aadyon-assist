"""System endpoints: health check and the aggregated dashboard summary.

/api/health is public (liveness probe). The data endpoints are per-user and are
guarded by get_current_user, which also binds the RLS context for their queries.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.db.session import query
from app.routers.auth import get_current_user
from app.services.summary import dashboard_summary
from app.services.digital_me import digital_me
from app.services.schema import entities_meta
from app.services.briefing import build_briefing

router = APIRouter(prefix="/api", tags=["system"])

# Applied per-route so /health can stay public.
_guard = [Depends(get_current_user)]


@router.get("/health")
def health():
    try:
        query("SELECT 1", commit=False)
        return {"status": "ok", "db": "up"}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"status": "degraded", "db": str(e)}, status_code=503)


@router.get("/summary", dependencies=_guard)
def summary():
    return dashboard_summary()


@router.get("/digital-me", dependencies=_guard)
def digital_me_view():
    """Identity + life-since-birth + four life-dimension scores, in one call."""
    return digital_me()


@router.get("/entities", dependencies=_guard)
def entities():
    """Schema metadata for every CRUD entity — powers the generic data admin UI."""
    return entities_meta()


@router.get("/briefing", dependencies=_guard)
def briefing():
    """Today's life-ops briefing as Markdown (also written to artifacts/ daily)."""
    return {"markdown": build_briefing()}
