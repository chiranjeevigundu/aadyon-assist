"""System endpoints: health check and the aggregated dashboard summary.

/api/health is public (liveness probe). The data endpoints are per-user and are
guarded by get_current_user, which also binds the RLS context for their queries.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.db.session import query
from app.routers.auth import get_current_user
from app.services.summary import dashboard_summary
from app.services.schema import entities_meta
from app.services.briefing import build_briefing
from app.services.alerts import build_alerts

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


@router.get("/app-config")
def app_config():
    """Public, non-sensitive UI flags. Lets the frontend render the right chrome
    (dev links, invite field) without hardcoding deployment policy."""
    s = get_settings()
    return {"dev_mode": s.dev_mode, "invite_required": s.invite_required}


@router.get("/summary", dependencies=_guard)
def summary():
    return dashboard_summary()


@router.get("/entities", dependencies=_guard)
def entities():
    """Schema metadata for every CRUD entity — powers the generic data admin UI."""
    return entities_meta()


@router.get("/alerts", dependencies=_guard)
def alerts():
    """What needs attention in the next ALERT_DAYS days (deadlines, bills)."""
    return build_alerts()


@router.get("/briefing", dependencies=_guard)
def briefing():
    """Today's life-ops briefing as Markdown (also written to artifacts/ daily)."""
    return {"markdown": build_briefing()}
