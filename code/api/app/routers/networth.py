"""Net worth endpoints: the summary read-model and daily snapshotting.

Per-user; guarded by get_current_user (which binds the RLS context) in main.py.
"""
from fastapi import APIRouter

from app.services import networth

router = APIRouter(prefix="/api/networth", tags=["networth"])


@router.get("")
def summary():
    """Totals (assets, liabilities, net worth), the asset breakdown, and history."""
    return networth.net_worth_summary()


@router.post("/snapshot")
def snapshot():
    """Record today's net worth into the time series (idempotent per day)."""
    return networth.take_snapshot()
